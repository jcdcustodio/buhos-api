import argparse
import sys
from pathlib import Path

import duckdb
import joblib

DIR_WH = Path("./data/warehouse").resolve()
DIR_SQL = Path("./sql").resolve()
DIR_GOLD = DIR_WH / "gold"
PATH_DB = DIR_WH / "buhos_db.duckdb"
PATH_MODEL = Path("./csp_model.joblib").resolve()

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

TRAIN_COLS = [
    "sample_id",
    "src"
] + FEATURE_COLS + ["compressive_strength"]


def execute_sql_file(con: duckdb.DuckDBPyConnection, sql_file: str) -> None:
    sql_path = DIR_SQL / sql_file
    if not sql_path.exists():
        raise FileNotFoundError(f"[ERROR] Missing SQL definition: {sql_path}")
    query = sql_path.read_text(encoding="utf-8")
    con.execute(query)


def verify_silver_build(con: duckdb.DuckDBPyConnection) -> int:
    """Confirm validation ran and silver contains valid records before building gold."""
    audit_row = con.execute("""
        SELECT valid_count, evaluated_at
        FROM silver_cs.data_quality_audit_logs
        ORDER BY evaluated_at DESC
        LIMIT 1
    """).fetchone()

    if not audit_row or audit_row[0] <= 0:
        raise RuntimeError(
            "[ERROR] Gold build aborted: no valid records logged in silver_cs.data_quality_audit_logs."
        )
    return int(audit_row[0])


def export_training_set(con: duckdb.DuckDBPyConnection) -> None:
    """Stage 1 (Pre-Training): Export canonical 12-column training set from valid silver rows."""

    DIR_GOLD.mkdir(parents=True, exist_ok=True)
    PQ_TRAIN = DIR_GOLD / "model_train_set.parquet"

    con.execute("CREATE SCHEMA IF NOT EXISTS gold_cs;")
    execute_sql_file(con, "01_train_set.sql")
    con.execute(f"COPY gold_cs.model_train_set TO '{PQ_TRAIN}' (FORMAT PARQUET);")

    exported_train_df = con.execute(f"SELECT * FROM read_parquet('{PQ_TRAIN}')").df()
    assert list(exported_train_df.columns) == TRAIN_COLS, (
        f"Training column mismatch: {list(exported_train_df.columns)}"
    )

    print(
        "----- Model Training Set Export -----\n"
        f"Source     : silver_cs.valid_samples\n"
        f"Table      : gold_cs.model_train_set ({len(exported_train_df)} rows)\n"
        f"Parquet    : {PQ_TRAIN.name}\n"
        "Next Step  : Run training script 'train.py' to generate model file 'csp_model.joblib'\n"
        "-------------------------------------"
    )


def build_sem_analytics(con: duckdb.DuckDBPyConnection) -> None:
    """Stage 2 (Post-Training): Score valid rows with trained model and build star schema + QC layer."""

    if not PATH_MODEL.exists():
        raise FileNotFoundError(
            f"[ERROR] Trained model not found at {PATH_MODEL}.\n"
            "Tip: Export training set 'build_gold.py ml' and run training script 'train.py' before building the semantic layer."
        )

    DIR_GOLD.mkdir(parents=True, exist_ok=True)
    PQ_SEM_QC = DIR_GOLD / "sem_analytics.parquet"

    valid_df = con.execute("SELECT * FROM silver_cs.valid_samples").df()
    model_pipeline = joblib.load(PATH_MODEL)
    valid_df["predicted_strength"] = model_pipeline.predict(valid_df[FEATURE_COLS]).astype("float64")

    con.register("temp_scored_valid_samples", valid_df)
    con.execute("CREATE SCHEMA IF NOT EXISTS gold_cs;")

    # Build dimensions, fact table, and semantic QC view in dependency order
    sql_steps = [
        "02_dim_source.sql",
        "03_dim_mix_design.sql",
        "04_fact_concrete_tests.sql",
        "05_sem_analytics_qc.sql",
    ]
    for sql_file in sql_steps:
        execute_sql_file(con, sql_file)

    con.execute(f"COPY gold_cs.sem_analytics_qc TO '{PQ_SEM_QC}' (FORMAT PARQUET);")

    mix_count = con.execute("SELECT COUNT(*) FROM gold_cs.dim_mix_design").fetchone()[0]
    fact_count = con.execute("SELECT COUNT(*) FROM gold_cs.fact_concrete_tests").fetchone()[0]

    print(
        "----- Quality Control Semantic Layer -----\n"
        f"Model Used : {PATH_MODEL.name}\n"
        f"Dimensions : gold_cs.dim_source, gold_cs.dim_mix_design ({mix_count} unique mixes)\n"
        f"Fact Table : gold_cs.fact_concrete_tests ({fact_count} test records)\n"
        f"Semantic   : gold_cs.sem_analytics_qc -> {PQ_SEM_QC.name}\n"
        "------------------------------------------"
    )


def build_sem_dq(con: duckdb.DuckDBPyConnection) -> None:
    """Build data quality semantic views for monitoring valid vs. quarantined records."""

    con.execute("CREATE SCHEMA IF NOT EXISTS gold_cs;")
    execute_sql_file(con, "06_sem_data_quality.sql")

    quarantined_rows = con.execute("SELECT COUNT(*) FROM silver_cs.quarantine_samples").fetchone()[0]
    rule_violations = con.execute("SELECT COUNT(*) FROM gold_cs.sem_dq_quarantine_details").fetchone()[0]

    print(
        "----- Data Quality Semantic Layer -----\n"
        f"Views Created     : gold_cs.sem_dq_quarantine_details, gold_cs.sem_dq_run_summary\n"
        f"Quarantined Rows  : {quarantined_rows}\n"
        f"Rule Violations   : {rule_violations}\n"
        "---------------------------------------"
    )


def run_gold_build() -> None:
    parser = argparse.ArgumentParser(
        description="Build Gold layer artifacts (export training set, build semantic layers)."
    )
    parser.add_argument(
        "stage",
        choices=["train", "qc", "dq"],
        help=(
            "'trains' exports the pre-training dataset; "
            "'qc' builds the post-training star schema and QC semantic layer; "
            "'dq' builds the data quality monitoring views"
        ),
    )

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    with duckdb.connect(str(PATH_DB)) as con:
        verify_silver_build(con)
        if args.stage == "train":
            export_training_set(con)
        elif args.stage == "qc":
            build_sem_analytics(con)
        elif args.stage == "dq":
            build_sem_dq(con)


if __name__ == "__main__":
    run_gold_build()