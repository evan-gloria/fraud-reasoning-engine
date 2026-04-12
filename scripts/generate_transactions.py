"""
generate_transactions.py

Generates 5,000 synthetic retail banking credit card transactions for use
in testing the Vertex AI Reasoning Engine Text-to-SQL capabilities.

Outputs:
  - scripts/transactions_seed.csv (local inspection)

Usage:
  python scripts/generate_transactions.py

To also load into BigQuery:
  python scripts/generate_transactions.py --load-bq
"""

import argparse
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from faker import Faker

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

FAKE = Faker("en_AU")
NUM_RECORDS = 5_000
FRAUD_RATE = 0.035  # ~3.5% fraud rate
OUTPUT_CSV = Path(__file__).parent / "transactions_seed.csv"
GCP_REGION = os.environ.get("GCP_REGION", "US")

# Merchant category codes with realistic weights
MCC_POOL = [
    ("5411", "Grocery Stores"),
    ("5812", "Eating Places & Restaurants"),
    ("5999", "Miscellaneous Retail"),
    ("5912", "Drug Stores & Pharmacies"),
    ("5541", "Service Stations"),
    ("5732", "Electronics Stores"),
    ("5945", "Hobby, Toy & Game Shops"),
    ("7011", "Hotels & Motels"),
    ("4111", "Transportation"),
    ("6011", "ATM / Cash Advance"),
]
MCC_CODES = [m[0] for m in MCC_POOL]
MCC_NAMES = [m[1] for m in MCC_POOL]
MCC_WEIGHTS = [0.25, 0.20, 0.15, 0.10, 0.08, 0.07, 0.05, 0.04, 0.04, 0.02]

# Currency pool — predominantly AUD
CURRENCIES = ["AUD", "USD", "EUR", "GBP", "JPY", "SGD"]
CURRENCY_WEIGHTS = [0.92, 0.03, 0.02, 0.01, 0.01, 0.01]

# Country pool — predominantly Australia
COUNTRIES = ["Australia", "United States", "United Kingdom", "France", "Japan", "Singapore"]
COUNTRY_WEIGHTS = [0.91, 0.04, 0.02, 0.01, 0.01, 0.01]

# ---------------------------------------------------------------------------
# Dataset generation
# ---------------------------------------------------------------------------


def _generate_amounts(n: int, fraud_mask: np.ndarray) -> np.ndarray:
    """
    Generates transaction amounts skewed toward normal retail values,
    with higher-value outliers more likely in fraudulent transactions.
    """
    rng = np.random.default_rng(42)

    # Legitimate: Gamma distribution centred around ~$65 AUD
    legit_amounts = rng.gamma(shape=2.5, scale=26.0, size=n).round(2)
    legit_amounts = np.clip(legit_amounts, 0.50, 2_000.0)

    # Fraudulent: Mix of high-value and normal amounts
    fraud_n = fraud_mask.sum()
    fraud_amounts = np.where(
        rng.random(fraud_n) < 0.6,
        rng.uniform(500, 5_000, fraud_n).round(2),   # 60% — high value
        rng.gamma(shape=2.5, scale=26.0, size=fraud_n).round(2),  # 40% — blend in
    )

    amounts = legit_amounts.copy()
    amounts[fraud_mask] = fraud_amounts
    return amounts


def _generate_risk_scores(fraud_mask: np.ndarray, amounts: np.ndarray) -> np.ndarray:
    """
    Generates risk scores [0.0, 1.0] highly correlated with is_flagged,
    with realistic noise so it's not a perfect predictor.
    """
    rng = np.random.default_rng(99)
    n = len(fraud_mask)

    # Legitimate: clustered low with right-tail noise
    legit_base = rng.beta(a=1.5, b=8.0, size=n)

    # Fraudulent: clustered high with left-tail noise
    fraud_base = rng.beta(a=7.0, b=2.0, size=n)

    scores = np.where(fraud_mask, fraud_base, legit_base)

    # Small nudge from high amounts (normalised)
    amount_nudge = (np.log1p(amounts) / np.log1p(amounts.max())) * 0.15
    scores = np.clip(scores + amount_nudge * fraud_mask, 0.0, 1.0)

    return scores.round(4)


def generate_dataset(num_records: int = NUM_RECORDS) -> pd.DataFrame:
    """
    Generates a DataFrame of synthetic retail banking credit card transactions.

    Args:
        num_records: Number of records to generate.

    Returns:
        pd.DataFrame with the full transaction schema.
    """
    rng = np.random.default_rng(7)
    now = datetime.now(tz=timezone.utc)

    # --- Fraud mask -----------------------------------------------------------
    fraud_mask = rng.random(num_records) < FRAUD_RATE

    # --- Timestamps -----------------------------------------------------------
    offsets_seconds = rng.integers(0, 60 * 24 * 3600, size=num_records)
    timestamps = [
        now - timedelta(seconds=int(s)) for s in offsets_seconds
    ]

    # --- MCCs -----------------------------------------------------------------
    mcc_indices = rng.choice(len(MCC_CODES), size=num_records, p=MCC_WEIGHTS)

    # --- Currencies & countries -----------------------------------------------
    # Fraud transactions more likely to be international
    currency_p = np.where(
        fraud_mask[:, None],
        np.array([[0.5, 0.15, 0.12, 0.08, 0.08, 0.07]]),  # fraud — more intl
        np.array([CURRENCY_WEIGHTS]),
    )
    currencies = [
        rng.choice(CURRENCIES, p=p) for p in currency_p
    ]

    country_p = np.where(
        fraud_mask[:, None],
        np.array([[0.45, 0.20, 0.12, 0.10, 0.07, 0.06]]),  # fraud — more intl
        np.array([COUNTRY_WEIGHTS]),
    )
    countries = [
        rng.choice(COUNTRIES, p=p) for p in country_p
    ]

    # --- Amounts & risk scores ------------------------------------------------
    amounts = _generate_amounts(num_records, fraud_mask)
    risk_scores = _generate_risk_scores(fraud_mask, amounts)

    # --- Assemble DataFrame ---------------------------------------------------
    df = pd.DataFrame(
        {
            "transaction_id": [str(uuid.uuid4()) for _ in range(num_records)],
            "customer_id": [f"CUST_{rng.integers(10_000_000, 99_999_999)}" for _ in range(num_records)],
            "transaction_timestamp": timestamps,
            "merchant_name": [FAKE.company() for _ in range(num_records)],
            "merchant_category_code": [MCC_CODES[i] for i in mcc_indices],
            "transaction_amount": amounts,
            "currency": currencies,
            "is_flagged": fraud_mask,
            "risk_score": risk_scores,
            "location_country": countries,
            "terminal_id": [f"TERM_{rng.integers(1000, 9999)}" for _ in range(num_records)],
        }
    )

    print(f"✅ Generated {num_records:,} records.")
    print(f"   Fraud rate: {fraud_mask.mean():.2%} ({fraud_mask.sum()} flagged)")
    print(f"   Avg amount: ${amounts.mean():.2f} AUD")
    print(f"   Avg risk score: {risk_scores.mean():.4f}")
    return df


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


def save_to_csv(df: pd.DataFrame, file_path: str | Path = OUTPUT_CSV) -> None:
    """
    Saves the DataFrame to a CSV file.

    Args:
        df: The transactions DataFrame.
        file_path: Output path. Defaults to scripts/transactions_seed.csv.
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"💾 CSV saved to: {path.resolve()}")


# ---------------------------------------------------------------------------
# BigQuery loader
# ---------------------------------------------------------------------------


def load_to_bigquery(
    df: pd.DataFrame,
    project_id: str | None = None,
    dataset_id: str = "retail_banking",
    table_id: str = "credit_card_transactions",
    truncate: bool = False,
) -> None:
    """
    Loads the transactions DataFrame directly into BigQuery.

    Reads GCP_PROJECT from the environment if project_id is not provided.
    Authentication uses Application Default Credentials (ADC). Run:
        gcloud auth application-default login

    Args:
        df: The transactions DataFrame.
        project_id: GCP project ID. Falls back to GCP_PROJECT env var.
        dataset_id: BigQuery dataset name. Default: retail_banking.
        table_id: BigQuery table name. Default: credit_card_transactions.
        truncate: If True, overwrites the table. Default: False (Append).
    """
    from google.cloud import bigquery  # lazy import — only required for BQ path

    project_id = project_id or os.environ.get("GCP_PROJECT")
    if not project_id:
        raise ValueError(
            "No GCP project ID provided. Set GCP_PROJECT in your .env file "
            "or pass project_id explicitly."
        )

    full_table_id = f"{project_id}.{dataset_id}.{table_id}"
    client = bigquery.Client(project=project_id)

    # Ensure dataset exists, create it if not
    dataset_ref = bigquery.Dataset(f"{project_id}.{dataset_id}")
    dataset_ref.location = GCP_REGION
    try:
        client.get_dataset(dataset_ref)
        print(f"📂 Dataset {project_id}.{dataset_id} already exists.")
    except Exception:
        client.create_dataset(dataset_ref, exists_ok=True)
        print(f"📂 Created dataset {project_id}.{dataset_id}.")

    # Explicit schema to guarantee correct BigQuery types
    schema = [
        bigquery.SchemaField("transaction_id", "STRING", description="Unique identifier assigned to a discrete financial transaction"),
        bigquery.SchemaField("customer_id", "STRING", description="Unique identifier for user"),
        bigquery.SchemaField("transaction_timestamp", "TIMESTAMP", description="The exact time the transaction occurred"),
        bigquery.SchemaField("merchant_name", "STRING", description="Name of merchant"),
        bigquery.SchemaField("merchant_category_code", "STRING", description="A standard four-digit number used by credit card processors to classify a business by the type of goods or services it provides."),
        bigquery.SchemaField("transaction_amount", "FLOAT64", description="Monetary value of a single financial transaction"),
        bigquery.SchemaField("currency", "STRING", description="ISO 4217 currency code such as USD or EUR"),
        bigquery.SchemaField("is_flagged", "BOOLEAN", description="Whether the transaction was flagged by the ML model"),
        bigquery.SchemaField("risk_score", "FLOAT64", description="Quantitative assessment of the financial risk associated with an entity or transaction"),
        bigquery.SchemaField("location_country", "STRING", description="Country where the transaction occurred"),
        bigquery.SchemaField("terminal_id", "STRING", description="Payment terminal identifier"),
    ]

    disposition = bigquery.WriteDisposition.WRITE_TRUNCATE if truncate else bigquery.WriteDisposition.WRITE_APPEND
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=disposition,
    )

    print(f"⬆️  Loading {len(df):,} rows to {full_table_id} ...")
    job = client.load_table_from_dataframe(df, full_table_id, job_config=job_config)
    job.result()  # Wait for completion
    print(f"✅ BigQuery load complete: {full_table_id}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic credit card transaction data.")
    parser.add_argument(
        "--load-bq",
        action="store_true",
        help="Also load the generated data into BigQuery.",
    )
    parser.add_argument(
        "--num-records",
        type=int,
        default=None,
        help="Number of records to generate (default: random 5-20).",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Overwrite the BigQuery table instead of appending (Warning: deletes existing data).",
    )
    args = parser.parse_args()

    # Default to 5-20 records if not specified, or 5,000 if truncate is used
    if args.num_records is not None:
        count = args.num_records
    elif args.truncate:
        count = NUM_RECORDS
    else:
        rng = np.random.default_rng()
        count = int(rng.integers(5, 21))

    transactions_df = generate_dataset(num_records=count)
    save_to_csv(transactions_df)

    if args.load_bq:
        load_to_bigquery(transactions_df, truncate=args.truncate)
