import datetime
import hashlib
import uuid
from pathlib import Path

import duckdb
import pandas as pd
import yaml

DIR_RAW = Path("./data/raw").resolve()
DIR_WH = Path("./data/warehouse").resolve()
DIR_BRONZE = DIR_WH / "bronze"
PATH_CONFIG = Path("./sources.yaml").resolve()
PATH_DB = DIR_WH / "buhos_db.duckdb"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_raw_file(file_path: Path, source_config: dict) -> pd.DataFrame:
    ext = file_path.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(
            file_path,
            header=None,
            dtype=str,
            sep=source_config.get("delimiter", ","),
            encoding=source_config.get("encoding", "utf-8-sig"),
            keep_default_na=False
        )
    if ext in {".xls", ".xlsx", ".xlsm", ".xlsb", ".ods"}:
        return pd.read_excel(
            file_path,
            header=None,
            dtype=str,
            engine="calamine",
        )
    raise ValueError(f"Unsupported file extension '{ext}' for {file_path.name}")


def run_ingestion() -> None:
    with PATH_CONFIG.open("r", encoding="utf-8") as file:
        sources = yaml.safe_load(file)["sources"]

    DIR_BRONZE.mkdir(parents=True, exist_ok=True)
    batch_id = str(uuid.uuid4())
    ingested_at = datetime.datetime.now(datetime.UTC).isoformat()

    with duckdb.connect(str(PATH_DB)) as con:
        con.execute("CREATE SCHEMA IF NOT EXISTS bronze_cs;")

        for src_id, src_cfg in sources.items():
            matched_files = sorted(DIR_RAW.glob(src_cfg["file_pattern"]))
            if not matched_files:
                print(
                    f"[WARNING] Bronze: No files matched '{src_cfg["file_pattern"]}' for '{src_id}'"
                )

            source_frames = []
            for file_path in matched_files:
                raw_df = read_raw_file(file_path=file_path, source_config=src_cfg)
                raw_df.columns = [f"col_{i}" for i in range(raw_df.shape[1])]

                # Attach historical lineage and audit metadata
                raw_df["_ingest_batch_id"] = batch_id
                raw_df["_source_id"] = src_id
                raw_df["_source_file"] = file_path.name
                raw_df["_file_sha256"] = file_sha256(file_path)
                raw_df["_raw_row_num"] = range(1, len(raw_df) + 1)
                raw_df["_ingested_at"] = ingested_at

                source_frames.append(raw_df)
                print(f"Bronze: Captured {len(raw_df)} raw rows from {file_path.name}")

            combined_raw = pd.concat(source_frames, ignore_index=True)
            parquet_path = DIR_BRONZE / f"{src_id}_{batch_id[:8]}.parquet"
            combined_raw.to_parquet(parquet_path, index=False)

            # Append-only historical table in bronze schema
            con.execute(f"""
                CREATE TABLE IF NOT EXISTS bronze_cs.{src_id} AS
                SELECT * FROM read_parquet('{parquet_path}') WHERE 1=0;
            """)
            con.execute(f"""
                INSERT INTO bronze_cs.{src_id}
                SELECT * FROM read_parquet('{parquet_path}');
            """)


if __name__ == "__main__":
    run_ingestion()