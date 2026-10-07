"""Generate tiny, wholly invented MIMIC-shaped tables; contains no patient data."""
import argparse
import csv
from datetime import datetime, timedelta
from pathlib import Path
from renalwatch.mimic import SCHEMAS


def generate(root):
    root = Path(root)
    if root.exists() and any(root.iterdir()):
        raise ValueError('Mock destination must be empty')
    tables = {name: [] for name in SCHEMAS}
    tables['hosp/d_labitems'] = [{'itemid': '50912', 'label': 'Creatinine', 'fluid': 'Blood'}]
    tables['icu/d_items'] = [
        {'itemid': '220045', 'label': 'Heart Rate'},
        {'itemid': '220052', 'label': 'Arterial Blood Pressure mean'},
        {'itemid': '220181', 'label': 'Non Invasive Blood Pressure mean'}]
    start = datetime(2150, 1, 1)
    def stamp(hours):
        return (start + timedelta(hours=hours)).isoformat(sep=' ')
    # 1 rise; 2 observed no rise; 3 no follow-up; 4 prior rise;
    # 5 discharged early; 6 late pre-cutoff lab cannot leak into features;
    # 7 missing storetime retained for label only; 8 missing HR;
    # 9 insufficient baseline; 10 conflicting same-time creatinine.
    for sid in range(1, 11):
        ids = {'subject_id': str(sid), 'hadm_id': str(100 + sid), 'stay_id': str(200 + sid)}
        tables['hosp/patients'].append({'subject_id': str(sid), 'anchor_age': 50, 'anchor_year': 2150})
        tables['hosp/admissions'].append({**ids, 'admittime': stamp(-12), 'dischtime': stamp(72), 'deathtime': ''})
        tables['icu/icustays'].append({**ids, 'intime': stamp(0), 'outtime': stamp(36 if sid == 5 else 72)})
        labs = [(0, 1.0, 1), (20, 1.1, 21), (47, 1.1, 48)]
        if sid == 1:
            labs[-1] = (30, 1.4, 31)
        if sid == 3:
            labs.pop()
        if sid == 4:
            labs[1] = (20, 1.4, 21)
        if sid == 6:
            labs[1] = (20, 1.1, 26)
        if sid == 7:
            labs[1] = (20, 1.1, None)
        if sid == 9:
            labs.pop(0)
        if sid == 10:
            labs.append((20, 1.8, 22))
        for hour, value, availability in labs:
            tables['hosp/labevents'].append({**ids, 'itemid': '50912', 'charttime': stamp(hour),
                'storetime': stamp(availability) if availability is not None else '',
                'valuenum': value, 'valueuom': 'mg/dL'})
        for item, value, unit in [('220052', 80, 'mmHg'), ('220045', 85, 'bpm')]:
            if sid == 8 and item == '220045':
                continue
            tables['icu/chartevents'].append({**ids, 'itemid': item, 'charttime': stamp(23),
                'storetime': stamp(23.25), 'valuenum': value, 'valueuom': unit})
    for table, data in tables.items():
        path = root / (table + '.csv')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=SCHEMAS[table], extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)
    return root


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=Path('data/mock_mimic'))
    args = p.parse_args()
    generate(args.output)
    print('Invented test records written to ' + str(args.output))
