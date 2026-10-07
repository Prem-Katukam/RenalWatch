"""Train an integration-test model on fabricated labels, NOT clinical AKI labels."""
import argparse
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss, confusion_matrix
from .features import FEATURES

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mlflow', action='store_true')
    args = parser.parse_args()
    rng = np.random.default_rng(42)
    count = 800
    data = pd.DataFrame({
        'creatinine_latest': rng.uniform(.5, 3, count),
        'creatinine_change': rng.normal(.1, .3, count),
        'map_latest': rng.normal(80, 12, count),
        'heart_rate_latest': rng.normal(85, 15, count),
    })
    # Entirely fabricated data-generating process, not a medical definition.
    logits = -3 + .8 * data.iloc[:, 0] + 2 * data.iloc[:, 1] - .035 * (data.iloc[:, 2] - 80)
    labels = rng.binomial(1, 1 / (1 + np.exp(-logits)))
    ids = np.arange(count)  # One independent fabricated record per synthetic patient.
    train, test = train_test_split(ids, test_size=.25, random_state=42, stratify=labels)
    model = make_pipeline(SimpleImputer(strategy='median', add_indicator=True), StandardScaler(), LogisticRegression(random_state=42))
    model.fit(data.iloc[train][FEATURES], labels[train])
    probabilities = model.predict_proba(data.iloc[test][FEATURES])[:, 1]
    tn, fp, fn, tp = confusion_matrix(labels[test], probabilities >= .5, labels=[0, 1]).ravel()
    metrics = { 'auroc': float(roc_auc_score(labels[test], probabilities)),
        'average_precision': float(average_precision_score(labels[test], probabilities)),
        'brier_score': float(brier_score_loss(labels[test], probabilities)),
        'sensitivity_at_0_5': float(tp / (tp + fn)),
        'specificity_at_0_5': float(tn / (tn + fp)),
        'test_prevalence': float(labels[test].mean()) }
    output = Path('artifacts'); output.mkdir(exist_ok=True)
    joblib.dump(model, output / 'demo_model.joblib')
    report = {'mode': 'SYNTHETIC_DEMO_ONLY', 'clinical_validation': False,
        'label': 'fabricated binary outcome; not AKI', 'train_patients': len(train),
        'test_patients': len(test), 'seed': 42, 'metrics': metrics}
    (output / 'demo_metrics.json').write_text(json.dumps(report, indent=2))
    if args.mlflow:
        import mlflow
        mlflow.set_tracking_uri('sqlite:///mlflow.db')
        mlflow.set_experiment('renalwatch-synthetic-integration')
        with mlflow.start_run():
            mlflow.set_tag('data_mode', 'synthetic_only')
            mlflow.log_params({'seed': 42, 'model': 'logistic_regression', 'patients': count})
            mlflow.log_metrics(metrics)
            mlflow.log_artifact(str(output / 'demo_metrics.json'))
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
