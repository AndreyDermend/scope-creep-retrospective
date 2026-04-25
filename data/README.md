# Data

This project uses the **Telco Customer Churn** dataset.

## Source

- **Origin:** IBM Sample Data Sets — Telco Customer Churn
- **Mirror used by this project:** https://github.com/IBM/telco-customer-churn-on-icp4d
- **Direct CSV:** https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv
- **License:** The CSV is distributed by IBM as a sample dataset in a public repository. No row-level PII is present; all `customerID` values are synthetic.

## Shape

- 7,043 rows × 21 columns (20 features + `Churn` target)
- Binary target: `Churn` ∈ {`Yes`, `No`}, ~26.5% positive rate
- Mix of categorical (e.g., `Contract`, `InternetService`) and numeric (`tenure`, `MonthlyCharges`, `TotalCharges`)

## What the pipeline does with it

`src/scope_creep/data_prep.py` downloads the CSV, drops 11 rows where
`TotalCharges` is blank, removes the `customerID` column, shuffles with a
fixed seed, and splits 80/20 into:

- `training.csv` — with the `Churn` label (5,626 rows)
- `scoring.csv`  — no label, this is what Andrey's model predicts on (1,407 rows)

The split is deterministic (`random_state=42`) so runs are reproducible.

## Local cache

Running `make run` writes `training.csv` and `scoring.csv` to the project
root (they're gitignored). Delete them to force a re-download.
