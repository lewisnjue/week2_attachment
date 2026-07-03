"""Export preprocessed real estate listings from MongoDB to a clean modeling CSV."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import pandas as pd

from boma_analytics.db import get_collection, get_mongo_db

SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[2]
OUTPUT_DIR = PROJECT_ROOT / "data"

COLLECTION_NAME = "unified_listings"
DEFAULT_OUTPUT_FILE = "boma_listings_modeling.csv"


def export_collection_to_csv(output_path: Path) -> None:
    # Ensure the target 'data' directory exists before writing
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Connecting to database to fetch data from '{COLLECTION_NAME}'...")
    db = get_mongo_db()
    collection = get_collection(COLLECTION_NAME, db=db)

    # Fetch all documents, projecting out fields irrelevant to training
    projection = {
        "_id": 0,
        "source_id": 0,
        "processed_at": 0,
        "scraped_at": 0
    }

    cursor = collection.find({}, projection)
    documents = list(cursor)

    if not documents:
        print("Warning: No records found in the unified collection. Did you run the preprocessor first?")
        return

    print(f"Retrieved {len(documents)} records. Converting to DataFrame...")

    # Load into Pandas
    df = pd.DataFrame(documents)

    # Quick structural alignment (Ensuring target column is the first feature for convenience)
    if "price_ksh" in df.columns:
        cols = ["price_ksh"] + \
            [col for col in df.columns if col != "price_ksh"]
        df = df[cols]

    # Save to CSV using the absolute Path object
    df.to_csv(output_path, index=False)

    print("\n--- Export Summary ---")
    print(f"File saved successfully to: {output_path.resolve()}")
    print(f"Total Rows: {df.shape[0]}")
    print(f"Total Columns/Features: {df.shape[1]}")
    print(f"Feature Matrix Shape: {df.shape}")
    print("\nColumns exported:")
    for col in df.columns:
        missing_count = df[col].isna().sum()
        missing_pct = (missing_count / len(df)) * 100
        print(f" - {col:<18} | Missing: {missing_count:<5} ({missing_pct:.1f}%)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dump clean MongoDB modeling data to a standard CSV file."
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_FILE,
        help="Filename or explicit path for the destination CSV file.",
    )
    args = parser.parse_args()

    # 2. Smart path construction
    provided_output = Path(args.output)
    if provided_output.is_absolute():
        final_output_path = provided_output
    else:
        # If it's just a file name or relative path, force it into the root data directory
        final_output_path = OUTPUT_DIR / provided_output

    export_collection_to_csv(final_output_path)


if __name__ == "__main__":
    main()
