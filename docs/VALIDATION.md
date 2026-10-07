# Validation of starter package

Executed in the build environment:
- Nine tests passed: six feature-integrity checks and three API integration checks.
- Synthetic model training and held-out metric export completed (600 training records, 200 test records).
- Python source compilation passed.

Limitations:
- Docker is unavailable in the build environment; image build is not verified.
- MLflow optional integration has not been executed here.
- Clinical data, labels, model performance, deployment and latency are not validated.
- Requirements use compatibility ranges, not a verified dependency lockfile.

## MIMIC adapter update — 2026-10-07

- Python 3.12: all 30 unittest cases passed (9 existing, 21 new).
- Invented MIMIC-shaped CSV generation and CLI processing completed end to end.
- Gzip input, dictionary mismatch, overwrite protection, late results, missing
  follow-up, censoring, threshold boundaries, future-baseline leakage, conflicting
  labs and invalid-unit ascertainment covered by automated tests.
- Fixture output: 10 rows; 1 observed rise, 4 observed no rise, 1 prior rise excluded,
  1 censored, 1 unknown baseline, 1 unknown follow-up, 1 conflicting-lab unknown.
- Existing synthetic model training and API tests passed. A Starlette/httpx
  deprecation warning remains non-fatal.
- No restricted MIMIC data used. Full dataset runtime/memory, clinical labels,
  dialysis exclusions and clinical performance remain unvalidated.
