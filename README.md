# RenalWatch

Kidney-injury early-warning research project. **Version 0.1 is a runnable synthetic integration starter, not an AKI model or clinically validated product.**

## Implemented
- As-of feature construction with separate measurement and result-availability timestamps.
- Unit validation, missing-input abstention, and stale-input warnings.
- Reproducible synthetic training and held-out evaluation.
- FastAPI inference source, Dockerfile, optional MLflow tracking.
- Tests for future-data leakage, late results, units, ordering, and invalid values.

## Windows quick start (PowerShell, Python 3.11)
Open a terminal in this folder, where requirements.txt is located.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m renalwatch.train_demo
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m uvicorn renalwatch.api:app --host 127.0.0.1 --port 8000
```
Open http://127.0.0.1:8000/docs. Expand POST /predict-demo, choose Try it out, and paste example_request.json. A demo score is NOT a probability of AKI. /health reports service status and model-file presence, not clinical readiness.

## macOS / Linux
```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m renalwatch.train_demo
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m uvicorn renalwatch.api:app --host 127.0.0.1 --port 8000
```

## Optional MLflow
Run training with --mlflow, then launch `mlflow ui --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1`. The experiment is tagged synthetic_only. Training artifacts are generated locally and excluded from Git.

## Optional Docker
```bash
docker build -t renalwatch:0.1 .
docker run --rm -p 127.0.0.1:8000:8000 renalwatch:0.1
```
The image generates a synthetic model during the build. Dependencies have compatibility ranges; a verified lockfile remains a subsequent environment milestone.

## Not yet implemented
Validated clinical cohort/labels; real clinical training; SHAP; clinical NLP; active learning; Power BI; Azure ingestion and AKS. No clinical accuracy, HIPAA compliance, business savings, or latency target is claimed.

See docs/PROTOCOL.md and docs/SETUP_CHECKLIST.md before working with real data.

## Local dashboard

After training the demo model, start the API with the existing Uvicorn command and open http://127.0.0.1:8000/. No additional packages are needed. The dashboard includes editable synthetic observations, separate-unit trend charts, sample scenarios, service status, and the actual `/predict-demo` response. All times in the editor are UTC. A negative hours-before value means after prediction time. Scores concern a fabricated outcome, not AKI risk.

Changing inputs clears the previous result. Late or out-of-window results are excluded from charts, and the API independently applies its eligibility checks. The dashboard stores no inputs in browser storage and uses no external scripts.

## MIMIC processing prototype

A local CSV/gzip adapter, invented MIMIC-shaped fixtures, patient-level splits and
a provisional creatinine-rise endpoint are now implemented. Real-data validation,
dialysis exclusions and clinical training remain pending. Nothing changes the
synthetic dashboard model. See [the processing guide](docs/MIMIC_PIPELINE.md) for
Windows commands, required tables, endpoint rules and limitations.
