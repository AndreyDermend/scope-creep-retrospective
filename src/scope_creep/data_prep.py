"""Download Telco Customer Churn and split into training/scoring CSVs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

TELCO_URL = (
    "https://raw.githubusercontent.com/IBM/"
    "telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv"
)


def prepare_data(
    data_dir: str | Path = ".",
    test_fraction: float = 0.2,
    seed: int = 42,
    url: str = TELCO_URL,
) -> tuple[Path, Path]:
    """Download Telco Churn, split into training.csv and scoring.csv.

    Returns (training_path, scoring_path).
    """
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(url)

    # TotalCharges comes in as object with blank strings — coerce
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
    df = df.dropna(subset=["TotalCharges"]).reset_index(drop=True)

    # customerID is not a feature
    df = df.drop(columns=["customerID"])

    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)
    split_idx = int(len(df) * (1 - test_fraction))
    training = df.iloc[:split_idx].copy()
    scoring = df.iloc[split_idx:].drop(columns=["Churn"]).copy()

    training_path = data_dir / "training.csv"
    scoring_path = data_dir / "scoring.csv"
    training.to_csv(training_path, index=False)
    scoring.to_csv(scoring_path, index=False)

    return training_path, scoring_path


if __name__ == "__main__":
    tp, sp = prepare_data()
    print(f"Wrote {tp} and {sp}")
