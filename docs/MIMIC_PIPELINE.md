# MIMIC-IV processing prototype

Status: implemented and tested on wholly invented records only. No restricted data has
been accessed. This does not train, replace, or deploy a clinical model. The existing
synthetic dashboard is unchanged. All output rows have `clinical_ready=False`.

## Try it now (PowerShell, project root)

No additional dependencies are needed for the adapter.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m renalwatch.mock_mimic --output data/mock_mimic
.\.venv\Scripts\python.exe -m renalwatch.mimic --root data/mock_mimic --output data/mock_processed --source invented-fixtures
```

Both generators refuse to overwrite a nonempty destination. On a second run, choose
new directory names. Outputs: `cohort.csv` (one landmark per selected patient) and
`audit.json` (counts, feature allowlist, protocol ID and outstanding review gates).
The adapter has no network calls and downloads nothing.

## Required inputs after approved MIMIC access

Point `--root` at a directory containing `hosp/` and `icu/`. Each table may be
`.csv` or `.csv.gz` (gzip takes precedence if both exist).

| Folder | Required tables | Purpose |
| --- | --- | --- |
| hosp | patients, admissions | Approximate adult age, admission/discharge/death times |
| hosp | labevents, d_labitems | Blood creatinine and dictionary check |
| icu | icustays | First ICU stay, landmark and observation end |
| icu | chartevents, d_items | Heart rate and mean arterial pressure |

```powershell
.\.venv\Scripts\python.exe -m renalwatch.mimic --root "D:\mimiciv\3.1" --output data/mimic_processed_v1 --max-stays 1000 --source mimic-iv-3.1
```

This is a bounded pilot, not a full dataset benchmark. It scans the large event
files sequentially and retains relevant events for at most 1,000 selected stays by
default. A full scan can still take substantial time; runtime and peak memory on
real MIMIC are unmeasured. Metadata tables are loaded into memory. Increasing the
cap increases retained events and memory. The selected subset is sorted by subject
ID, not a representative random sample. Do not use pilot estimates as final results.

## Fixed protocol: creatinine-rise-landmark-v0.1

- Select each subject's first ICU stay before checking eligibility; do not substitute
  a later stay if that first stay fails. Approximate age is anchor_age plus ICU-entry
  year minus anchor_year. Retain adults alive and observed in ICU past 24 hours.
- Prediction landmark is ICU entry +24 hours; outcome horizon is the following
  24 hours. This is a single-landmark study, not repeated real-time alerts.
- Features reuse the API's four-feature builder: latest creatinine, observed
  creatinine change, latest MAP, latest heart rate. Only measurements in the last
  24 hours with storetime at or before the landmark contribute. Missing or invalid
  storetime never falls back to charttime. Missing values remain blank, with warnings.
- Labs join by subject and time, including labs without hadm_id; this intentionally
  allows earlier-admission/outpatient baselines in the bounded lookback. Vitals
  require matching subject, admission and ICU stay. Lab item 50912 must resolve to
  blood creatinine in the dictionary. HR 220045; MAP 220052 and 220181. The existing
  builder chooses the higher value when simultaneous feature measurements tie;
  source prioritization remains a real-data audit item.
- Read up to 14 days of creatinine history so a prior rise in the last seven days
  can be compared with its own earlier baseline. Identical lab tuples deduplicate
  for labels. Conflicting creatinine at the same time makes the label unknown.
- At each measured creatinine, compare strictly earlier samples: increase >=0.3
  mg/dL relative to the lowest observed value within 48 hours, or >=1.5 times the
  lowest observed value within seven days. These are study operationalizations
  of the 2012 KDIGO creatinine criteria, not full KDIGO diagnosis or staging.
- A rise measured within seven days before the landmark (including the landmark)
  excludes the row, even if the result arrived late. Retrospective exclusion is
  separate from information used as predictor features.
- Require at least two distinct measured creatinine timestamps in the pre-landmark
  seven days. Otherwise baseline is unknown. This is a minimum data rule; it does
  NOT establish a normal baseline or rule out AKI already present on arrival.
- Outcome measurements use charttime, regardless of delayed/missing storetime.
  An observed rise after the landmark and before the horizon/observation end is
  positive. ICU exit, hospital discharge or death ends observation. A rise before
  censoring remains positive. Without a rise, early exit is censored; missing a
  creatinine in the final six hours is unknown. Otherwise label is observed no rise.
  A negative only means no rise in the observed samples, not proven absence of AKI.
- Invalid numeric measurements and unrecognized units are dropped and counted.
  No guessed unit conversions. An invalid lab within the labeling window (or with
  an unparseable timestamp for the selected subject) makes its label unknown.
  Their effect on ascertainment must be audited.
- MIMIC times remain shifted wall-clock times. UTC is attached only inside the
  feature-builder adapter to preserve time differences, not as a statement about
  the original clinical timezone. Never split patients by globally sorted shifted
  dates: shifts differ across patients.
- Stable SHA-256 subject-based buckets target 70% train /15% validation /15% test.
  Fractions are approximate, particularly in a small pilot. No stratification or
  temporal generalization claim. No imputation, scaling or threshold tuning occurs.

## Output interpretation

`target_creatinine_rise_24h` is 1, 0, or blank. Always inspect `label_status`:
`observed_rise`, `observed_no_rise`, `excluded_prior_rise`, `unknown_baseline`,
`unknown_followup`, `unknown_conflicting_labs`, `unknown_lab_quality`, or `censored`.
Feature warnings are independent of the label: a measured outcome can coexist with
missing predictors. The audit explicitly lists allowed feature columns; never feed
identifiers, onset time, label status, targets or prediction timestamps into a model.

## Required before clinical training

1. Audit actual version, item dictionaries, units, availability, duplicate/corrected
   values, missingness and exclusion rates against official derived concepts.
2. Implement and review ESRD/chronic dialysis and acute renal replacement therapy
   exclusions using appropriate event/diagnosis tables and timing. These are NOT
   implemented here; neither are CKD strata, transplant rules, or urine-output AKI.
3. Review baseline coverage and preexisting AKI. The observed-minimum approach can
   miss AKI already present on arrival. Avoid retrospective backfilled baselines.
4. Assess ascertainment bias from requiring follow-up labs and informative censoring;
   examine alternative follow-up and baseline definitions with a clinical reviewer.
5. Freeze cohort/endpoint version and review label cases before fitting a clinical
   model. Train transformations only on train; choose thresholds on validation;
   preserve the patient test partition. Keep synthetic scores separate.

Do not publish raw or derived patient-level MIMIC records. Use the approved local
processing environment and comply with your data agreement. `data/` is ignored by
Git. Keep real outputs there or outside the repository. No real records are needed
in chat. Publish code, invented fixtures and permitted aggregate results only.

## Primary references

- MIMIC-IV 3.1: https://physionet.org/content/mimiciv/3.1/
- Lab measurement vs availability and missing admission IDs:
  https://mimic.mit.edu/docs/iv/modules/hosp/labevents.html
- ICU measurement/storetime semantics:
  https://mimic.mit.edu/docs/iv/modules/icu/chartevents.html
- Age anchors: https://mimic.mit.edu/docs/iv/modules/hosp/patients.html
- Definition deliberately pinned to KDIGO 2012, section 2.1 (not a claim about
  the latest guideline):
  https://kdigo.org/wp-content/uploads/2016/10/KDIGO-2012-AKI-Guideline-English.pdf
- Official concepts for subsequent validation: https://github.com/MIT-LCP/mimic-code

No third-party SQL is copied or executed by this adapter.
