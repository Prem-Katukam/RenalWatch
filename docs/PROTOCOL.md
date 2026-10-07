# Research protocol — provisional, requires data audit

## Objective
Evaluate incident acute kidney injury within 24 hours after an eligible prediction time, using only information available then. The starter's fabricated outcome is unrelated to this endpoint.

## Decisions before clinical training
1. Confirm MIMIC access, dataset version, license conditions and permitted processing environment.
2. Specify adult ICU cohort, time origin, repeated prediction schedule, minimum history, and exclusions.
3. Select and document a published AKI definition. A creatinine-only endpoint must explicitly exclude claims of full urine-output-based detection. Define baseline creatinine handling and exclude existing AKI at prediction time.
4. Define outcome ascertainment: absent follow-up labs do not establish no AKI. Handle discharge, death, censoring, dialysis and chronic renal disease explicitly.
5. Fix patient-level training/validation/test assignments before fitting imputers or tuning thresholds. Keep all admissions and time windows for a patient together.
6. Use recorded availability times where available; explicitly document proxies and their limitations. Exclude discharge summaries and post-outcome treatment information from early-warning features.

## Evaluation
Compare logistic regression and a tree model against a simple pre-specified baseline. Fit transformations on training data only. Select thresholds on validation data. Evaluate once on held-out patients. Report AUROC, average precision, prevalence, Brier score, calibration, sensitivity, positive predictive value, false alerts per patient-day, and first-warning lead time. Define alert suppression and repeated-event handling before measurement. Bootstrap uncertainty at patient level.

## Explainability
SHAP is planned for model contributions, not causal reasoning. Validate explanation stability and show feature timestamps/missingness. NLP is deferred until suitable pre-prediction notes and labels exist.

## Publication
Publish code, schema, configuration, synthetic fixtures and aggregated permitted results. Keep restricted records, notes, patient-level outputs, secrets and credentials out of Git and public demos. Check applicable data agreement before cloud processing or sharing derived artifacts. The assistant does not need the user's PhysioNet password or restricted files in chat.

## Sources to consult before endpoint implementation
MIMIC-IV: https://physionet.org/content/mimiciv/3.1/
MIMIC access: https://mimic.mit.edu/docs/gettingstarted/
MIMIC demo: https://physionet.org/content/mimic-iv-demo/2.2/
Official derived-concept code: https://github.com/MIT-LCP/mimic-code
Clinical definition and concept-code version must be reviewed and pinned before label implementation.

## Implemented processing prototype

The versioned, provisional single-landmark creatinine-rise specification is in
[MIMIC_PIPELINE.md](MIMIC_PIPELINE.md). It is tested on invented fixtures only.
Outstanding clinical review items above remain required; the pipeline marks every
row clinical_ready=False and does not train a model.
