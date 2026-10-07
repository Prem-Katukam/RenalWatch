import contextlib
import csv
from datetime import datetime, timedelta
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest

from renalwatch.mimic import asof_features, build, endpoint, normalize, rises, split_for
from renalwatch.mock_mimic import generate
from collections import Counter

T = datetime(2150, 1, 2)
H = timedelta(hours=1)


class EndpointTests(unittest.TestCase):
    def test_absolute_threshold_and_boundary(self):
        self.assertEqual(rises([(T - 48*H, 1), (T, 1.3)]), [T])
        self.assertEqual(rises([(T - 48*H - timedelta(seconds=1), 1), (T, 1.3)]), [])

    def test_ratio_seven_day_boundary(self):
        self.assertEqual(rises([(T - 168*H, .4), (T, .6)]), [T])
        self.assertEqual(rises([(T - 168*H - timedelta(seconds=1), .4), (T, .6)]), [])

    def test_future_low_value_is_not_baseline(self):
        self.assertEqual(rises([(T, 2), (T + H, 1)]), [])

    def test_no_comparison_between_simultaneous_samples(self):
        self.assertEqual(rises([(T, 1), (T, 2)]), [])

    def test_prior_rise_at_cutoff_is_excluded(self):
        self.assertEqual(endpoint([(T-2*H, 1), (T, 1.3), (T+H, 2)], T, T+24*H)[1], 'excluded_prior_rise')

    def test_no_followup_is_unknown(self):
        self.assertEqual(endpoint([(T-2*H, 1), (T-H, 1)], T, T+24*H)[:2], (None, 'unknown_followup'))

    def test_positive_before_censoring_is_retained(self):
        labs = [(T-2*H, 1), (T-H, 1), (T+H, 1.3)]
        self.assertEqual(endpoint(labs, T, T+2*H)[0], 1)

    def test_negative_requires_complete_followup(self):
        labs = [(T-2*H, 1), (T-H, 1), (T+18*H, 1)]
        self.assertEqual(endpoint(labs, T, T+24*H)[0], 0)
        self.assertEqual(endpoint(labs, T, T+23*H)[1], 'censored')

    def test_after_horizon_ignored(self):
        labs = [(T-2*H, 1), (T-H, 1), (T+23*H, 1), (T+25*H, 3)]
        self.assertEqual(endpoint(labs, T, T+48*H)[0], 0)

    def test_measurement_after_death_ignored(self):
        labs = [(T-2*H, 1), (T-H, 1), (T+4*H, 2)]
        self.assertEqual(endpoint(labs, T, T+2*H)[1], 'censored')

    def test_availability_is_required_for_features(self):
        obs = [{'name': 'creatinine', 'unit': 'mg/dL', 'value': v,
                'measured': t, 'available': a} for t, a, v in
               [(T-H, T-H, 1), (T, T+H, 5), (T-H, None, 6), (T+H, T+H, 8)]]
        self.assertEqual(asof_features(obs, T)[0]['creatinine_latest'], 1)

    def test_reject_wrong_units_and_nan(self):
        row = {'itemid': '50912', 'charttime': str(T), 'storetime': str(T), 'valuenum': '1', 'valueuom': 'mmol/L'}
        audit = Counter()
        self.assertIsNone(normalize(row, audit))
        row.update(valueuom='mg/dL', valuenum='nan')
        self.assertIsNone(normalize(row, audit))
        self.assertEqual(audit['unexpected_unit'], 1)
        self.assertEqual(audit['invalid_measurement'], 1)

    def test_patient_split_is_stable(self):
        self.assertEqual(split_for(42), split_for('42'))
        self.assertEqual({split_for(i) for i in range(1000)}, {'train', 'validation', 'test'})


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = generate(Path(self.temp.name) / 'input')
        self.output = Path(self.temp.name) / 'output'

    def run_build(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return build(self.root, self.output, source='invented-fixtures')

    def test_end_to_end_expected_cases(self):
        results, report = self.run_build()
        cases = {int(r['subject_id']): r for r in results}
        expected = {1: 'observed_rise', 2: 'observed_no_rise', 3: 'unknown_followup',
                    4: 'excluded_prior_rise', 5: 'censored', 6: 'observed_no_rise',
                    7: 'observed_no_rise', 8: 'observed_no_rise', 9: 'unknown_baseline',
                    10: 'unknown_conflicting_labs'}
        self.assertEqual({k: r['label_status'] for k, r in cases.items()}, expected)
        self.assertEqual(cases[6]['creatinine_latest'], 1)
        self.assertEqual(cases[7]['creatinine_latest'], 1)
        self.assertIn('Missing recent heart_rate', cases[8]['feature_warnings'])
        self.assertFalse(report['clinical_ready'])
        self.assertEqual(json.loads((self.output / 'audit.json').read_text())['selected_stays'], 10)
        with (self.output / 'cohort.csv').open() as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[2]['target_creatinine_rise_24h'], '')

    def test_invalid_followup_does_not_become_negative(self):
        path = self.root / 'hosp/labevents.csv'
        path.write_text(path.read_text().replace('2150-01-02 23:00:00,2150-01-03 00:00:00,1.1,mg/dL',
                                                '2150-01-02 23:00:00,2150-01-03 00:00:00,1.1,unknown'))
        rows, _ = self.run_build()
        r = next(r for r in rows if r['subject_id'] == '2')
        self.assertEqual(r['label_status'], 'unknown_lab_quality')
        self.assertIsNone(r['target_creatinine_rise_24h'])

    def test_gzip_tables_supported(self):
        for file in self.root.rglob('*.csv'):
            with gzip.open(str(file) + '.gz', 'wb') as f:
                f.write(file.read_bytes())
            file.unlink()
        self.assertEqual(len(self.run_build()[0]), 10)

    def test_missing_table_fails(self):
        (self.root / 'hosp/labevents.csv').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing table'):
            self.run_build()

    def test_dictionary_mismatch_fails(self):
        path = self.root / 'hosp/d_labitems.csv'
        path.write_text(path.read_text().replace('Blood', 'Urine'))
        with self.assertRaisesRegex(ValueError, 'blood creatinine'):
            self.run_build()

    def test_refuses_overwrite(self):
        self.run_build()
        with self.assertRaisesRegex(ValueError, 'not empty'):
            self.run_build()

    def test_first_icu_stay_only(self):
        path = self.root / 'icu/icustays.csv'
        with path.open('a') as f:
            f.write('1,101,999,2150-01-01 01:00:00,2150-01-04 00:00:00\n')
        rows, _ = self.run_build()
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[0]['stay_id'], '201')

    def test_late_preexisting_rise_excluded_retrospectively(self):
        path = self.root / 'hosp/labevents.csv'
        path.write_text(path.read_text().replace('2150-01-01 20:00:00,2150-01-01 21:00:00,1.4',
                                                '2150-01-01 20:00:00,2150-01-02 02:00:00,1.4'))
        rows, _ = self.run_build()
        r = next(r for r in rows if r['subject_id'] == '4')
        self.assertEqual(r['label_status'], 'excluded_prior_rise')
        self.assertEqual(r['creatinine_latest'], 1)


if __name__ == '__main__':
    unittest.main()
