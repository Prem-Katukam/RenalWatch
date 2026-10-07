"""Local-only synthetic demo API. Not a deployed clinical service."""
from pathlib import Path
from typing import Literal
import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from .features import FEATURES, build_features

app = FastAPI(title='RenalWatch — synthetic research demo', version='0.1.0')
_model = None

class Observation(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    name: Literal['creatinine', 'map', 'heart_rate']
    value: float = Field(gt=0)
    unit: str
    measured_at: str
    available_at: str

class Request(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prediction_time: str
    observations: list[Observation] = Field(min_length=1, max_length=1000)

@app.get('/health')
def health():
    return {'status': 'ok', 'mode': 'synthetic_demo_only', 'model_file_present': Path('artifacts/demo_model.joblib').exists()}

@app.post('/predict-demo')
def predict(request: Request):
    global _model
    try:
        features, warnings = build_features([o.model_dump() for o in request.observations], request.prediction_time)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if any(w.startswith('Missing recent') for w in warnings):
        return {'mode': 'synthetic_demo_only', 'status': 'abstained', 'warnings': warnings, 'demo_score': None}
    if _model is None:
        path = Path('artifacts/demo_model.joblib')
        if not path.exists():
            raise HTTPException(status_code=503, detail='Run python -m renalwatch.train_demo first')
        # Load only the locally trained artifact; never accept uploaded pickle/joblib files.
        _model = joblib.load(path)
    score = float(_model.predict_proba(pd.DataFrame([features], columns=FEATURES))[0, 1])
    return {'mode': 'synthetic_demo_only', 'status': 'scored', 'demo_score': score,
        'meaning': 'Probability of a fabricated outcome, NOT kidney-injury risk', 'warnings': warnings}
