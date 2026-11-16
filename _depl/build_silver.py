import datetime
import hashlib
import json
import re
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import yaml

DIR_WH = Path("./data/warehouse").resolve()
DIR_SILVER = DIR_WH / "silver"
PATH_CONFIG = Path("./sources.yaml").resolve()
PATH_DB = DIR_WH / "buhos_db.duckdb"

FEATURE_COLS = [
    "cement", 
    "blast_furnace_slag", 
    "fly_ash", 
    "silica_fume", 
    "coarse_aggregate", 
    "fine_aggregate", 
    "water", 
    "superplasticizer", 
    "age"
]
NUMERIC_COLS = FEATURE_COLS + ["compressive_strength"]

METADATA_COLS = [
    "_ingest_batch_id", 
    "_source_id", 
    "_source_file", 
    "_file_sha256", 
    "_raw_row_num", 
    "_ingested_at"
]


def clean_header(text: str) -> str:
    """Collapse newlines and repeated whitespace from wrapped Excel headers."""
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def parse_bronze_source(raw_df: pd.DataFrame, source_id: str, config: dict) -> pd.DataFrame:
    """Extract header row, skip unit rows, map aliases, and apply unit factors."""

    # Convert 0-based config to 1-based `_raw_row_num`
    header_excel_row = config["header_rows"][0] + 1

    skip_after = config.get("skip_rows_after_header", 0)
    data_start_row = header_excel_row + 1 + skip_after

    parsed_sources = []
    for (src_file, batch_id), file_df in raw_df.groupby(["_source_file", "_ingest_batch_id"]):
        file_df = file_df.sort_values("_raw_row_num").reset_index(drop=True)

        # Extract header names from designated header row
        header_row = file_df.loc[file_df["_raw_row_num"] == header_excel_row].iloc[0]
        data_cols = [c for c in file_df.columns if c.startswith("col_")]
        col_names = [clean_header(header_row[c]) for c in data_cols]

        # Filter to actual data rows
        records = file_df.loc[file_df["_raw_row_num"] >= data_start_row].copy()
        renamed = pd.DataFrame(index=records.index)
        for raw_c, clean_name in zip(data_cols, col_names):
            renamed[clean_name] = records[raw_c]

        # Map canonical columns (keep raw string values for row-level DQ type checks)
        out_df = pd.DataFrame(index=records.index)
        for raw_alias, spec in config["column_map"].items():
            if raw_alias not in renamed.columns:
                raise ValueError(f"Schema drift in {src_file}: missing '{raw_alias}'")
            out_df[spec["target"]] = renamed[raw_alias]
            out_df[f"_mult_{spec['target']}"] = spec.get("unit_factor", 1.0)

        for target_col, default_val in config.get("defaults", {}).items():
            if target_col not in out_df.columns:
                out_df[target_col] = str(default_val)
                out_df[f"_mult_{target_col}"] = 1.0

        # Preserve bronze lineage metadata
        for meta_col in METADATA_COLS:
            out_df[meta_col] = records[meta_col].values

        parsed_sources.append(out_df)

    return pd.concat(parsed_sources, ignore_index=True)


def evaluate_and_route(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Validate rows against DQ rules, deduplicate, and split valid vs. quarantine."""
    rule_ids_per_row: list[list[str]] = [[] for _ in range(len(df))]
    reasons_per_row: list[list[str]] = [[] for _ in range(len(df))]

    def flag(mask: pd.Series, rule_id: str, reason: str) -> None:
        for idx in df.index[mask.fillna(True)]:
            rule_ids_per_row[idx].append(rule_id)
            reasons_per_row[idx].append(reason)

    # 1. Completeness (DQ-CMP-01) & Type Validity (DQ-VAL-01)
    numeric_df = pd.DataFrame(index=df.index)
    for col in NUMERIC_COLS:
        raw_series = df[col]
        is_missing = raw_series.isna() | (raw_series.astype(str).str.strip() == "")
        flag(is_missing, "DQ-CMP-01", f"Missing required value in '{col}'")

        parsed_num = pd.to_numeric(raw_series, errors="coerce") * df[f"_mult_{col}"]
        is_invalid_type = (~is_missing) & (parsed_num.isna() | ~np.isfinite(parsed_num))
        flag(is_invalid_type, "DQ-VAL-01", f"Non-numeric value '{raw_series}' in '{col}'")
        numeric_df[col] = parsed_num

    # 2. Domain Range Validity (DQ-VAL-02 & DQ-VAL-03)
    for col in ["cement", "water", "coarse_aggregate", "fine_aggregate", "compressive_strength"]:
        flag(numeric_df[col] <= 0, "DQ-VAL-02", f"'{col}' must be > 0")
    flag(numeric_df["age"] < 1, "DQ-VAL-02", "'age' must be >= 1 day")

    for col in ["blast_furnace_slag", "fly_ash", "silica_fume", "superplasticizer"]:
        flag(numeric_df[col] < 0, "DQ-VAL-03", f"'{col}' cannot be negative")

    # 3. Cross-Field Source Consistency (DQ-CON-01)
    src_violation = (df["_source_id"] == "src1") & (numeric_df["silica_fume"] != 0.0)
    flag(src_violation, "DQ-CON-01", "Source 1 (UCI) cannot contain non-zero silica_fume")

    # 4. Physical Reasonability (DQ-RSN-01 & DQ-RSN-02)
    ingredient_cols = [c for c in FEATURE_COLS if c != "age"]
    unit_weight = numeric_df[ingredient_cols].sum(axis=1)
    flag(~unit_weight.between(2100.0, 2600.0), "DQ-RSN-01", "Unit weight outside [2100, 2600] kg/m3")

    total_binder = (
        numeric_df["cement"]
        + numeric_df["blast_furnace_slag"]
        + numeric_df["fly_ash"]
        + numeric_df["silica_fume"]
    )
    ratio_wb = numeric_df["water"] / total_binder.replace(0, np.nan)
    flag(~ratio_wb.between(0.18, 0.95), "DQ-RSN-02", "Water-to-binder ratio outside [0.18, 0.95]")

    # 5. Deduplication / Uniqueness Check (DQ-UNQ-01)
    dedup_subset = pd.concat([df[["_source_id"]], numeric_df], axis=1)
    is_duplicate = dedup_subset.duplicated(keep="first")
    flag(is_duplicate, "DQ-UNQ-01", "Duplicate concrete sample record within source")

    # Assemble evaluated dataset
    evaluated = numeric_df.copy()
    for meta_col in METADATA_COLS:
        evaluated[meta_col] = df[meta_col].values

    evaluated["sample_id"] = [
        hashlib.md5(f"{s}:{f}:{r}".encode()).hexdigest()
        for s, f, r in zip(evaluated["_source_id"], evaluated["_source_file"], evaluated["_raw_row_num"])
    ]
    evaluated["failed_rule_count"] = [len(r) for r in rule_ids_per_row]
    evaluated["failed_rule_ids"] = [",".join(r) for r in rule_ids_per_row]
    evaluated["failure_reasons"] = [json.dumps(r) for r in reasons_per_row]

    # Split into valid vs. quarantine
    valid_mask = evaluated["failed_rule_count"] == 0
    valid_df = evaluated.loc[valid_mask].drop(
        columns=["failed_rule_count", "failed_rule_ids", "failure_reasons"]
    ).copy()
    valid_df["age"] = valid_df["age"].astype("int64")

    quarantine_df = evaluated.loc[~valid_mask].copy()

    # Build DQ monitoring summary for data quality dashboard
    eval_ts = datetime.datetime.now(datetime.UTC).isoformat()
    dq_audit_df = pd.DataFrame([{
        "evaluated_at": eval_ts,
        "total_evaluated": len(evaluated),
        "valid_count": len(valid_df),
        "quarantined_count": len(quarantine_df),
        "pass_rate_pct": round((len(valid_df) / max(len(evaluated), 1)) * 100, 2),
        "failure_rate_pct": round((len(quarantine_df) / max(len(evaluated), 1)) * 100, 2),
    }])

    return valid_df, quarantine_df, dq_audit_df


def run_silver_build() -> None:
    with PATH_CONFIG.open("r", encoding="utf-8") as f:
        sources = yaml.safe_load(f)["sources"]

    DIR_SILVER.mkdir(parents=True, exist_ok=True)
    valid_pq = DIR_SILVER / "valid_concrete_data.parquet"
    quarantine_pq = DIR_SILVER / "quarantine_concrete_data.parquet"
    dq_metrics_pq = DIR_SILVER / "data_quality_metrics.parquet"

    with duckdb.connect(str(PATH_DB)) as con:
        parsed_frames = []
        for source_id, cfg in sources.items():
            # Read latest ingested batch per file from bronze
            raw_df = con.execute(f"""
                SELECT * FROM bronze_cs.{source_id}
                QUALIFY ROW_NUMBER() OVER (
                    PARTITION BY _source_file, _raw_row_num
                    ORDER BY _ingested_at DESC
                ) = 1
            """).df()
            parsed_frames.append(parse_bronze_source(raw_df, source_id, cfg))

        all_parsed = pd.concat(parsed_frames, ignore_index=True)
        valid_df, quarantine_df, dq_audit_df = evaluate_and_route(all_parsed)

        valid_df.to_parquet(valid_pq, index=False)
        quarantine_df.to_parquet(quarantine_pq, index=False)
        dq_audit_df.to_parquet(dq_metrics_pq, index=False)

        con.execute("CREATE SCHEMA IF NOT EXISTS silver_cs;")
        con.execute(f"CREATE OR REPLACE TABLE silver_cs.valid_samples AS SELECT * FROM read_parquet('{valid_pq}');")
        con.execute(f"CREATE OR REPLACE TABLE silver_cs.quarantine_samples AS SELECT * FROM read_parquet('{quarantine_pq}');")
        con.execute("""
            CREATE TABLE IF NOT EXISTS silver_cs.data_quality_audit_logs (
                evaluated_at VARCHAR,
                total_evaluated INTEGER,
                valid_count INTEGER,
                quarantined_count INTEGER,
                pass_rate_pct DOUBLE,
                failure_rate_pct DOUBLE
            );
        """)
        con.execute(f"INSERT INTO silver_cs.data_quality_audit_logs SELECT * FROM read_parquet('{dq_metrics_pq}');")

    print(f"Silver: Evaluated {len(all_parsed)} records")
    print(
        "----- Validation Summary -----\n"
        f"Valid = {len(valid_df)} ({valid_pq.name})\n"
        f"Quarantined = {len(quarantine_df)} ({quarantine_pq.name})\n"
        "------------------------------"
    )


if __name__ == "__main__":
    run_silver_build()