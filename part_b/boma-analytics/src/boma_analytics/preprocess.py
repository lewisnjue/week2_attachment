"""Preprocess highly structured real estate records into a modeling-ready collection."""
from __future__ import annotations

import argparse
import hashlib
import re
import time
from typing import Any

from pymongo import UpdateOne
from pymongo.collection import Collection
from pymongo.database import Database

from boma_analytics.db import get_collection, get_mongo_db

SOURCE_COLLECTIONS = ["buyrentkenya", "property24"]
TARGET_COLLECTION_NAME = "unified_listings"

INTEGER_RE = re.compile(r"[-+]?[0-9]+")
NUMBER_RE = re.compile(r"[-+]?[0-9]+(?:[.,][0-9]+)?")
CURRENCY_RE = re.compile(r"[Kk] ?[Ss]?[Hh]?", re.IGNORECASE)
UNWANTED_CHARS_RE = re.compile(r"[^0-9.,-]+")


def clean_string(value: Any) -> str | None:
    if value is None:
        return None

    value_str = str(value).strip()
    if not value_str or value_str.lower() in {"n/a", "na", "none", "null", "nan"}:
        return None
    return value_str


def parse_integer(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)

    text = clean_string(value)
    if text is None:
        return None

    text = text.replace(",", "")
    digits = UNWANTED_CHARS_RE.sub("", text)
    if not digits or digits in {"-", "+"}:
        return None

    try:
        return int(float(digits))
    except ValueError:
        match = INTEGER_RE.search(text)
        return int(match.group()) if match else None


def parse_number(value: Any) -> float | None:
    """Parses numeric values and ignores units like 'm²' or 'sqft'."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = clean_string(value)
    if text is None:
        return None

    text = CURRENCY_RE.sub("", text)
    text = text.replace(",", "")

    match = NUMBER_RE.search(text)
    if not match:
        return None

    try:
        return float(match.group().replace(",", ""))
    except ValueError:
        return None


def normalize_price(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    text = clean_string(value)
    if text is None:
        return None

    text = CURRENCY_RE.sub("", text)
    text = text.replace(",", "").replace(" ", "")

    if not text or text in {"-", "+"}:
        return None

    try:
        return int(float(text))
    except ValueError:
        return parse_integer(text)


def normalize_property_type(raw_type: str | None) -> str:
    """Standardizes messy variations of property types for categorical encoding."""
    if not raw_type:
        return "Apartment"  # Baseline fallback imputation

    normalized = raw_type.lower()
    if "apartment" in normalized or "flat" in normalized:
        return "Apartment"
    if "townhouse" in normalized:
        return "Townhouse"
    if "house" in normalized or "villa" in normalized:
        return "House"
    if "land" in normalized or "plot" in normalized:
        return "Land"
    return "Other"


def build_source_id(source: str, raw_doc: dict[str, Any]) -> str:
    if source == "buyrentkenya":
        listing_id = raw_doc.get("listing_id") or raw_doc.get("_id")
        return str(listing_id)

    if source == "property24":
        title = clean_string(raw_doc.get("Title")) or ""
        address = clean_string(raw_doc.get("Address")) or ""
        price = clean_string(raw_doc.get("Price (KSh)")) or ""
        base = f"property24|{title}|{address}|{price}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()

    return hashlib.sha1(str(raw_doc).encode("utf-8")).hexdigest()


def unify_buyrentkenya(raw_doc: dict[str, Any]) -> dict[str, Any]:
    raw_type = clean_string(raw_doc.get("property_type"))

    return {
        "source": "buyrentkenya",
        "source_id": build_source_id("buyrentkenya", raw_doc),
        "price_ksh": normalize_price(raw_doc.get("price")),
        "property_type": normalize_property_type(raw_type),
        "bedrooms": parse_integer(raw_doc.get("bedrooms")),
        "bathrooms": None,  # Not structured in this specific source slice
        "parking": None,
        "floor_size_sqm": None,
        "location": clean_string(raw_doc.get("area")),
        "county": clean_string(raw_doc.get("county")),
        "scraped_at": raw_doc.get("scraped_at"),
    }


def unify_property24(raw_doc: dict[str, Any]) -> dict[str, Any]:
    title = clean_string(raw_doc.get("Title")) or ""

    return {
        "source": "property24",
        "source_id": build_source_id("property24", raw_doc),
        "price_ksh": normalize_price(raw_doc.get("Price (KSh)")),
        "property_type": normalize_property_type(title),
        "bedrooms": parse_integer(raw_doc.get("Bedrooms")),
        "bathrooms": parse_integer(raw_doc.get("Bathrooms")),
        "parking": parse_integer(raw_doc.get("Parking")),
        "floor_size_sqm": parse_number(raw_doc.get("Floor Size")),
        "location": clean_string(raw_doc.get("Location")),
        "county": clean_string(raw_doc.get("Location_Group")),
        "scraped_at": raw_doc.get("scraped_at"),
    }


def build_processed_document(source: str, raw_doc: dict[str, Any]) -> dict[str, Any]:
    if source == "buyrentkenya":
        doc = unify_buyrentkenya(raw_doc)
    elif source == "property24":
        doc = unify_property24(raw_doc)
    else:
        raise ValueError(f"Unsupported source tracking: {source}")

    doc["processed_at"] = time.time()
    return doc


def prepare_target_collection(collection: Collection) -> None:
    collection.create_index(
        [("source", 1), ("source_id", 1)],
        unique=True,
        name="idx_processed_source_source_id",
    )


def process_source_collection(source: str, db: Database, target_collection_name: str) -> int:
    source_collection = get_collection(source, db=db)
    target_collection = get_collection(target_collection_name, db=db)
    prepare_target_collection(target_collection)

    operations = []
    processed_count = 0

    for raw_doc in source_collection.find():
        processed_doc = build_processed_document(source, raw_doc)

        operations.append(
            UpdateOne(
                {"source": processed_doc["source"],
                    "source_id": processed_doc["source_id"]},
                {"$set": processed_doc},
                upsert=True,
            )
        )

        if len(operations) >= 250:
            target_collection.bulk_write(operations)
            processed_count += len(operations)
            operations.clear()

    if operations:
        target_collection.bulk_write(operations)
        processed_count += len(operations)

    return processed_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a unified clean modeling matrix collection from raw MongoDB scraping inputs."
    )
    parser.add_argument(
        "--source",
        choices=SOURCE_COLLECTIONS + ["all"],
        default="all",
        help="Which clean database collection to process.",
    )
    parser.add_argument(
        "--target",
        default=TARGET_COLLECTION_NAME,
        help="The target destination collection for preprocessed outputs.",
    )
    args = parser.parse_args()

    db = get_mongo_db()
    processed = 0

    if args.source == "all":
        for source in SOURCE_COLLECTIONS:
            processed += process_source_collection(source, db, args.target)
    else:
        processed = process_source_collection(args.source, db, args.target)

    print(f"Successfully compiled {
          processed} dense training records into: '{args.target}'")


if __name__ == "__main__":
    main()
