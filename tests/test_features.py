import math
import unittest
from renalwatch.features import build_features

CUTOFF = '2026-01-02T12:00:00+00:00'
def row(value=1, measured='2026-01-02T10:00:00+00:00', available='2026-01-02T10:05:00+00:00'):
    return dict(name='creatinine', value=value, unit='mg/dL', measured_at=measured, available_at=available)

class FeatureTests(unittest.TestCase):
    def test_future_measurement_excluded(self):
        features, _ = build_features([row(), row(9, '2026-01-02T13:00:00+00:00', '2026-01-02T13:01:00+00:00')], CUTOFF)
        self.assertEqual(features['creatinine_latest'], 1)
    def test_late_result_excluded(self):
        features, _ = build_features([row(9, available='2026-01-02T13:00:00+00:00')], CUTOFF)
        self.assertTrue(math.isnan(features['creatinine_latest']))
    def test_units_rejected(self):
        item = row(); item['unit'] = 'umol/L'
        with self.assertRaises(ValueError): build_features([item], CUTOFF)
    def test_naive_time_rejected(self):
        with self.assertRaises(ValueError): build_features([row()], '2026-01-02T12:00:00')
    def test_change_uses_ordered_history(self):
        features, _ = build_features([row(2), row(1, '2026-01-02T09:00:00+00:00', '2026-01-02T09:05:00+00:00')], CUTOFF)
        self.assertEqual(features['creatinine_change'], 1)
    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError): build_features([row(float('nan'))], CUTOFF)

if __name__ == '__main__': unittest.main()
