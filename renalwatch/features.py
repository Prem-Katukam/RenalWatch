"""As-of feature construction. Never consumes future observations."""
from datetime import datetime, timedelta
import math

FEATURES = ['creatinine_latest', 'creatinine_change', 'map_latest', 'heart_rate_latest']
UNITS = {'creatinine': 'mg/dL', 'map': 'mmHg', 'heart_rate': 'bpm'}

def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamps must include a timezone')
    return parsed

def build_features(observations, prediction_time):
    cutoff = timestamp(prediction_time)
    history = {key: [] for key in UNITS}
    for row in observations:
        name = row['name']
        if name not in history:
            raise ValueError('Unsupported observation: ' + name)
        if row['unit'] != UNITS[name]:
            raise ValueError('Unexpected unit for ' + name)
        value = float(row['value'])
        if not math.isfinite(value) or value <= 0:
            raise ValueError('Values must be finite and positive')
        measured = timestamp(row['measured_at'])
        available = timestamp(row['available_at'])
        if available < measured:
            raise ValueError('Availability cannot precede measurement')
        if cutoff - timedelta(hours=24) <= measured <= cutoff and available <= cutoff:
            history[name].append((measured, value))
    for values in history.values():
        values.sort()
    def latest(name):
        return history[name][-1][1] if history[name] else float('nan')
    cr = history['creatinine']
    change = cr[-1][1] - cr[0][1] if len(cr) >= 2 else float('nan')
    warnings = ['Missing recent ' + name for name, values in history.items() if not values]
    for name, values in history.items():
        if values and cutoff - values[-1][0] > timedelta(hours=6):
            warnings.append('Latest ' + name + ' is older than six hours')
    return dict(zip(FEATURES, [latest('creatinine'), change, latest('map'), latest('heart_rate')])), warnings
