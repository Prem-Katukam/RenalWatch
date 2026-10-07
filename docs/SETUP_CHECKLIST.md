# Your setup checklist

## Do now
1. Confirm whether your PhysioNet account has approved MIMIC-IV access. 'I can register' and 'approved' are different states. No passwords needed.
2. Install Python 3.11, VS Code and Git if missing. Run the local quick start in README.md. Docker is optional for the first run.
3. Tell the assistant your operating system, RAM and whether an NVIDIA GPU is available. A GPU is not required for this starter.
4. Create a private GitHub repository named renalwatch when ready. Do not upload datasets or credentials. The archive has no remote connection configured.
5. Report the first error text if setup fails; remove tokens/passwords before sharing logs.

## Wait until the local pipeline works
Azure subscription and budget alert; Azure CLI; Docker Desktop; Databricks/ADF; Power BI. Do not provision AKS yet. Cloud architecture, processing permissions and cost cap should be settled first.

## Assistant's next implementation work
Data adapter and cohort auditing after access confirmation; clinical labels after definition review; train/validation/test pipeline; model comparison; explanation layer; dashboard and deployment configuration. We work through these in active sessions; this package does not schedule background work.

## Ten-day milestones
Days 1–2: environment, access, schema and cohort audit.
Days 3–4: labels, features and baselines.
Days 5–6: held-out evaluation and threshold analysis.
Days 7–8: API, explanations and experiment tracking.
Days 9–10: dashboard, reproducibility, deployment and demo.
Full-data access is a dependency for the clinical milestones. If unavailable, finish the synthetic software demonstration without clinical performance claims.
