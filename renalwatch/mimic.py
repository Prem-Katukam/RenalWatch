"""Local MIMIC-IV CSV adapter: provisional creatinine-rise cohort, not an AKI model."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path

from renalwatch.features import FEATURES, build_features

PROTOCOL = 'creatinine-rise-landmark-v0.1'
HOUR = timedelta(hours=1)
ITEMS = {'50912': ('creatinine', 'mg/dL'), '220045': ('heart_rate', 'bpm'),
         '220052': ('map', 'mmHg'), '220181': ('map', 'mmHg')}
SCHEMAS = {
    'hosp/patients': ['subject_id', 'anchor_age', 'anchor_year'],
    'hosp/admissions': ['subject_id', 'hadm_id', 'admittime', 'dischtime', 'deathtime'],
    'icu/icustays': ['subject_id', 'hadm_id', 'stay_id', 'intime', 'outtime'],
    'hosp/d_labitems': ['itemid', 'label', 'fluid'],
    'icu/d_items': ['itemid', 'label'],
    'hosp/labevents': ['subject_id', 'hadm_id', 'itemid', 'charttime', 'storetime', 'valuenum', 'valueuom'],
    'icu/chartevents': ['subject_id', 'hadm_id', 'stay_id', 'itemid', 'charttime', 'storetime', 'valuenum', 'valueuom'],
}


def rows(root, table):
    path = root / (table + '.csv.gz')
    if not path.exists():
        path = root / (table + '.csv')
    if not path.exists():
        raise ValueError('Missing table: ' + table + '.csv[.gz]')
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        missing = set(SCHEMAS[table]) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(table + ': missing columns ' + ', '.join(sorted(missing)))
        yield from reader


def dt(value):
    # MIMIC shifted wall-clock timestamps are timezone-naive. Do not reinterpret
    # as local machine time or claim that the original clinical timezone is UTC.
    t = datetime.fromisoformat(value)
    if t.tzinfo is not None:
        raise ValueError('Expected timezone-naive MIMIC timestamp')
    return t


def split_for(subject):
    bucket = int(hashlib.sha256(('renalwatch-v1:' + str(subject)).encode()).hexdigest()[:8], 16) % 100
    return 'train' if bucket < 70 else ('validation' if bucket < 85 else 'test')


def validate_dictionary(root):
    labs = {r['itemid']: r for r in rows(root, 'hosp/d_labitems')}
    vitals = {r['itemid']: r for r in rows(root, 'icu/d_items')}
    lab = labs.get('50912', {})
    if lab.get('label', '').lower() != 'creatinine' or lab.get('fluid', '').lower() != 'blood':
        raise ValueError('50912 must map to blood creatinine; audit d_labitems')
    for key, words in [('220045', ['heart', 'rate']), ('220052', ['blood', 'pressure', 'mean']),
                       ('220181', ['blood', 'pressure', 'mean'])]:
        if not all(w in vitals.get(key, {}).get('label', '').lower() for w in words):
            raise ValueError('Unexpected dictionary mapping for ' + key)


def normalize(row, audit):
    name, unit = ITEMS[row['itemid']]
    try:
        measured = dt(row['charttime'])
        value = float(row['valuenum'])
        if not math.isfinite(value) or value <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        audit['invalid_measurement'] += 1
        return None
    raw_unit = row['valueuom'].strip().lower().replace(' ', '')
    accepted = {'creatinine': {'mg/dl'}, 'heart_rate': {'bpm'}, 'map': {'mmhg'}}
    if raw_unit not in accepted[name]:
        audit['unexpected_unit'] += 1
        return None
    available = None
    try:
        available = dt(row['storetime'])
        if available < measured:
            available = None
    except (ValueError, TypeError):
        pass
    if available is None:
        audit['missing_or_invalid_availability'] += 1
    return {'name': name, 'unit': unit, 'value': value, 'measured': measured, 'available': available}


def rises(labs):
    """Observed increase, using strictly earlier samples only; no backfilled baseline."""
    result = []
    for t, value in sorted(set(labs)):
        prior7 = [v for p, v in labs if t - 168 * HOUR <= p < t]
        prior48 = [v for p, v in labs if t - 48 * HOUR <= p < t]
        if ((prior48 and value - min(prior48) >= 0.3 - 1e-9)
                or (prior7 and value >= 1.5 * min(prior7) - 1e-9)):
            result.append(t)
    return result


def endpoint(labs, cutoff, observed_until):
    end = cutoff + 24 * HOUR
    # 14 days history lets us compare a pre-cutoff event with its earlier 7-day baseline.
    labs = [(t, v) for t, v in labs if cutoff - 336 * HOUR <= t <= min(end, observed_until)]
    events = rises(labs)
    if any(cutoff - 168 * HOUR <= t <= cutoff for t in events):
        return None, 'excluded_prior_rise', None
    history = {t for t, _ in labs if cutoff - 168 * HOUR <= t <= cutoff}
    if len(history) < 2:
        return None, 'unknown_baseline', None
    future = [t for t in events if cutoff < t <= end]
    if future:
        return 1, 'observed_rise', min(future)
    if observed_until < end:
        return None, 'censored', None
    if not any(end - 6 * HOUR <= t <= end for t, _ in labs):
        return None, 'unknown_followup', None
    return 0, 'observed_no_rise', None


def asof_features(observations, cutoff):
    eligible = []
    for o in observations:
        if o['available'] is not None:
            # UTC is a computational placeholder only; preserves shifted time differences.
            eligible.append({'name': o['name'], 'unit': o['unit'], 'value': o['value'],
                             'measured_at': o['measured'].replace(tzinfo=timezone.utc).isoformat(),
                             'available_at': o['available'].replace(tzinfo=timezone.utc).isoformat()})
    return build_features(eligible, cutoff.replace(tzinfo=timezone.utc).isoformat())


def build(root, output, max_stays=1000, source='mimic-iv-3.1'):
    root, output = Path(root), Path(output)
    if max_stays < 1:
        raise ValueError('max_stays must be positive')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output directory is not empty; choose a new directory')
    validate_dictionary(root)
    audit = Counter()
    patients = {r['subject_id']: r for r in rows(root, 'hosp/patients')}
    admissions = {r['hadm_id']: r for r in rows(root, 'hosp/admissions')}
    # First ICU stay per subject is determined before duration/outcome selection.
    first = {}
    for r in rows(root, 'icu/icustays'):
        sid = r['subject_id']
        if sid not in first or (dt(r['intime']), int(r['stay_id'])) < (dt(first[sid]['intime']), int(first[sid]['stay_id'])):
            first[sid] = r
    cohort = []
    for sid, r in sorted(first.items(), key=lambda x: int(x[0])):
        audit['first_stays_considered'] += 1
        p, a = patients.get(sid), admissions.get(r['hadm_id'])
        if not p or not a or a['subject_id'] != sid:
            audit['missing_or_mismatched_demographics'] += 1
            continue
        start, stop = dt(r['intime']), dt(r['outtime'])
        age = int(p['anchor_age']) + start.year - int(p['anchor_year'])
        cutoff = start + 24 * HOUR
        admit, discharge = dt(a['admittime']), dt(a['dischtime'])
        if not admit <= start < stop <= discharge:
            audit['invalid_stay_interval'] += 1
            continue
        observed = min(stop, discharge, dt(a['deathtime']) if a['deathtime'] else stop)
        if age < 18 or observed <= cutoff:
            audit['underage_or_not_observed_at_landmark'] += 1
            continue
        cohort.append({**r, 'age_approx': age, 'cutoff': cutoff, 'observed': observed})
    total_eligible = len(cohort)
    cohort = cohort[:max_stays]
    by_subject = {r['subject_id']: r for r in cohort}
    observations = defaultdict(list)
    bad_lab_subjects = set()
    # Stream entire large tables; retain only selected subjects, items and time windows.
    for table in ['hosp/labevents', 'icu/chartevents']:
        print('Scanning ' + table + ' ...', flush=True)
        for r in rows(root, table):
            audit[table + '_rows_scanned'] += 1
            c = by_subject.get(r['subject_id'])
            if c is None or r['itemid'] not in ITEMS:
                continue
            lab = table == 'hosp/labevents'
            if lab and r['itemid'] != '50912':
                continue
            if not lab and (r['itemid'] == '50912' or r['stay_id'] != c['stay_id'] or r['hadm_id'] != c['hadm_id']):
                continue
            o = normalize(r, audit)
            if o is None:
                if lab:
                    try:
                        measured = dt(r['charttime'])
                        if c['cutoff'] - 336 * HOUR <= measured <= min(c['cutoff'] + 24 * HOUR, c['observed']):
                            bad_lab_subjects.add(c['subject_id'])
                    except (ValueError, TypeError):
                        bad_lab_subjects.add(c['subject_id'])
                continue
            lower = c['cutoff'] - (336 if lab else 24) * HOUR
            upper = min(c['cutoff'] + 24 * HOUR, c['observed']) if lab else c['cutoff']
            if lower <= o['measured'] <= upper:
                observations[c['subject_id']].append(o)
    result = []
    for c in cohort:
        obs = observations[c['subject_id']]
        lab_obs = [o for o in obs if o['name'] == 'creatinine']
        labels = [(o['measured'], o['value']) for o in lab_obs]
        # Conflicting simultaneous blood values make labels ambiguous: flag entire stay.
        values = defaultdict(set)
        for t, v in labels:
            values[t].add(v)
        target, status, onset = endpoint(labels, c['cutoff'], c['observed'])
        if any(len(v) > 1 for v in values.values()):
            target, status, onset = None, 'unknown_conflicting_labs', None
        if c['subject_id'] in bad_lab_subjects:
            target, status, onset = None, 'unknown_lab_quality', None
        feat, warnings = asof_features(obs, c['cutoff'])
        audit['endpoint_' + status] += 1
        row = {k: c[k] for k in ['subject_id', 'hadm_id', 'stay_id', 'age_approx']}
        row.update(prediction_time=c['cutoff'].isoformat(), split=split_for(c['subject_id']),
                   **{k: None if not math.isfinite(v) else v for k, v in feat.items()},
                   target_creatinine_rise_24h=target, label_status=status,
                   onset_time=onset.isoformat() if onset else '',
                   feature_warnings='; '.join(warnings), clinical_ready=False)
        result.append(row)
    output.mkdir(parents=True, exist_ok=True)
    fields = ['subject_id', 'hadm_id', 'stay_id', 'age_approx', 'prediction_time', 'split', *FEATURES,
              'target_creatinine_rise_24h', 'label_status', 'onset_time', 'feature_warnings', 'clinical_ready']
    with (output / 'cohort.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(result)
    report = {'protocol': PROTOCOL, 'source': source, 'clinical_ready': False,
              'eligible_before_cap': total_eligible, 'selected_stays': len(result), 'max_stays': max_stays,
              'audit': dict(audit), 'split_counts': dict(Counter(r['split'] for r in result)),
              'blocking_reviews': ['dialysis and ESRD exclusions', 'baseline and prevalent AKI ascertainment',
                                   'urine output endpoint omitted', 'real-data mapping and missingness audit'],
              'feature_columns': FEATURES,
              'never_use_as_features': ['target_creatinine_rise_24h', 'label_status', 'onset_time',
                                        'subject_id', 'hadm_id', 'stay_id', 'prediction_time']}
    (output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('Wrote cohort.csv and audit.json. PROVISIONAL: clinical_ready=false.', flush=True)
    return result, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--max-stays', type=int, default=1000)
    parser.add_argument('--source', default='mimic-iv-3.1')
    args = parser.parse_args()
    try:
        build(args.root, args.output, args.max_stays, args.source)
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
