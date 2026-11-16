# Data Engineering Pipeline for BuhosAPI

```mermaid
flowchart LR
    subgraph L1["Bronze"]
        RAW["Raw data files"]
        BRZ[("Bronze Storage")]
        RAW -->|Ingest| BRZ
    end

    subgraph L2["Silver (Validation and Quarantine)"]
        VAL_PROC["Normalize format, Deduplicate, Run DQ rules"]
        SILV_V[("Valid Data")]
        SILV_Q[("Quarantine Data")]
        BRZ --> VAL_PROC
        VAL_PROC -->|Pass| SILV_V
        VAL_PROC -->|Fail| SILV_Q
    end

    subgraph L3["Gold Layer"]
        G_ML[("ML Model Training Set")]
        G_DQ[("Data Quality Semantic Views")]
        G_QC[("Dimension and Fact Tables")]

        SILV_V --> G_ML
        SILV_Q --> G_DQ
        SILV_V --> G_QC
    end

    subgraph L4["ML Lifecycle and Analytics"]
        TRAIN["Prediction Model Pipeline"]
        BI_QC["Operational QC and Mix Dashboard"]
        BI_DQ["Data Quality Dashboard"]

        G_ML --> TRAIN
        TRAIN -->|Batch score| G_QC
        G_QC --> BI_QC
        G_DQ --> BI_DQ
    end
```

This section covers building a basic data pipeline with governance for BuhosAPI. In the original implementation ([see notebook for reference](../nb_eda_fe.ipynb)) the raw data was processed manually (data cleaning and preprocessing), which is practical enough with relatively small datasets. To support scale, validate data, and streamline model training, building a data pipeline becomes a necessity.

Specifically, the data pipeline allow us to do the following.

- Load, transform, and store records of concrete sample from different sources.
- Perform data quality checks to segregate valid samples from invalid ones.
- Export a clean training set for the model.
- Support analytics solutions, such as dashboards, that allow us to monitor quality of concrete samples and data quality in pipeline runs.

## Setup

This section shares the same project config as the main application. Thus the following commands applies for setting up the environment.

```bash
# Create virtual environment
uv venv --python 3.14

# Sync virtual environment to install dependencies
uv sync

# Optional: Include packages from dependency groups
uv sync --group dev

```

While in working directory, run the following commands as follows.

```bash
# Ingest raw data to bronze
uv run ingest_source.py

# Setup Silver (parse, transform, validate and quarantine data)
uv run build_silver.py

# Export training set
uv run build_gold.py train

# Run training scrip to create model file
uv run train.py

# Create semantic layer for analytics
uv run build_gold.py qc

# Create semantic view for data quality
uv run build_gold.py dq
```

## Process overview

- Create a local database with DuckDB.
- Setup config for raw dataset in `sources.yaml` that will be used by the scripts as reference for parsing.
- Append only raw tables and ingestion metadata in bronze schema.
- Parse raw tables to normalize formatting, deduplication, and row-level data quality checks in silver schema.
- Validated records goes to gold schema or exported for model training.
- Define dimension and fact tables, and semantic layers and views in gold schema.

## Gold schema

```mermaid
erDiagram
    DIM_SOURCE {
        VARCHAR src PK "Source identifier"
        VARCHAR source_description "Dataset or plant origin"
    }

    DIM_MIX_DESIGN {
        VARCHAR mix_design_id PK "MD5 hash of 8 rounded ingredient masses"
        DOUBLE cement "kg/m3"
        DOUBLE blast_furnace_slag "kg/m3"
        DOUBLE fly_ash "kg/m3"
        DOUBLE silica_fume "kg/m3"
        DOUBLE coarse_aggregate "kg/m3"
        DOUBLE fine_aggregate "kg/m3"
        DOUBLE water "kg/m3"
        DOUBLE superplasticizer "kg/m3"
        DOUBLE total_binder_kg_m3 "Sum of cementitious materials"
        DOUBLE unit_weight_kg_m3 "Total fresh concrete mass"
        DOUBLE ratio_wb "Water-to-binder ratio"
        DOUBLE pct_scm_repl "Percentage of SCM to total binder"
        DOUBLE pct_sp "Percent of superplasticizer to total binder"
        DOUBLE pct_slag "Percent of blast furnace slag to total binder"
        DOUBLE pct_fly_ash "Percent of fly ash to total binder"
        DOUBLE pct_silica_fume "Percent of silica fume to total binder"
    }

    FACT_CONCRETE_TESTS {
        VARCHAR sample_id PK "Deterministic test sample surrogate key"
        VARCHAR mix_design_id FK "References dim_mix_design"
        VARCHAR src FK "References dim_source"
        BIGINT age_days "Curing age in days"
        DECIMAL actual_strength_mpa "DECIMAL(10, 2) measured f'c"
        DECIMAL predicted_strength_mpa "DECIMAL(10, 2) model prediction"
        DECIMAL strength_residual_mpa "DECIMAL(10, 2) actual minus predicted"
        VARCHAR source_file "Originating Excel filename"
        BIGINT raw_row_num "1-based row number in raw file"
        VARCHAR ingested_at "UTC ingestion timestamp"
    }

    SEM_QC_ANALYTICS {
        VARCHAR sample_id PK "Denormalized test grain"
        VARCHAR mix_design_id "Joined mix key"
        VARCHAR src "Joined source key"
        VARCHAR source_description "From dim_source"
        DOUBLE cement "From dim_mix_design"
        DOUBLE blast_furnace_slag "From dim_mix_design"
        DOUBLE fly_ash "From dim_mix_design"
        DOUBLE silica_fume "From dim_mix_design"
        DOUBLE coarse_aggregate "From dim_mix_design"
        DOUBLE fine_aggregate "From dim_mix_design"
        DOUBLE water "From dim_mix_design"
        DOUBLE superplasticizer "From dim_mix_design"
        DOUBLE total_binder_kg_m3 "From dim_mix_design"
        DOUBLE unit_weight_kg_m3 "From dim_mix_design"
        DOUBLE ratio_wb "From dim_mix_design"
        DOUBLE pct_scm_repl "From dim_mix_design"
        BIGINT age_days "From fact_concrete_tests"
        DECIMAL actual_strength_mpa "From fact_concrete_tests"
        DECIMAL predicted_strength_mpa "From fact_concrete_tests"
        DECIMAL strength_residual_mpa "From fact_concrete_tests"
        DECIMAL moving_avg_3_mpa "Rolling 3-test average"
        DECIMAL rolling_std_30_mpa "Rolling 30-test standard deviation"
        DECIMAL cusum_residual_mpa "Cumulative sum of residuals"
    }

    DIM_SOURCE ||--o{ FACT_CONCRETE_TESTS : "classifies (src)"
    DIM_MIX_DESIGN ||--o{ FACT_CONCRETE_TESTS : "defines proportions (mix_design_id)"
    DIM_SOURCE ||..o{ SEM_QC_ANALYTICS : "enriches"
    DIM_MIX_DESIGN ||..o{ SEM_QC_ANALYTICS : "enriches"
    FACT_CONCRETE_TESTS ||..|| SEM_QC_ANALYTICS : "projects + SPC windows"
```

## Data Quality Rules

- The table shown summarizes the specific data quality rules implemented in the pipeline.
- Additional rules may be defined, such as specific limits in the amount of SCM added in the concrete mix.

| Rule ID | Data Quality Dimension | Table / Field | Rule Condition | Business Rationale | Failure Action |
| --- | --- | --- | --- | --- | --- |
| **DQ-CMP-01** | Completeness | All 9 input features + `compressive_strength` | Non-null after applying source defaults (e.g., `silica_fume = 0.0` for `src1`) | Missing mix weights or target strength corrupts binder ratios and model training. | Route to Quarantine |
| **DQ-VAL-01** | Validity | All numeric feature & target columns | Values must parse cleanly to valid finite numbers (`DOUBLE` / `INTEGER`) | Prevents text artifacts (e.g., `"N/A"`, stray headers) from entering Silver. | Route to Quarantine |
| **DQ-VAL-02** | Validity | `cement`, `water`, `coarse_aggregate`, `fine_aggregate`, `age`, `compressive_strength` | Strictly $> 0$ (`age >= 1` day). | Concrete cannot exist without cement, water, aggregates, curing age, or positive strength. | Route to Quarantine |
| **DQ-VAL-03** | Validity | `blast_furnace_slag`, `fly_ash`, `silica_fume`, `superplasticizer` | Greater than or equal to $0$ ($\ge 0$) | Supplementary cementitious materials (SCMs) and admixtures are optional ($0$), never negative. | Route to Quarantine |
| **DQ-CON-01** | Consistency | `source_id`, `silica_fume` | e.g., If `source_id == 'src1'` then `silica_fume == 0.0` | Enforces known dataset provenance. | Route to Quarantine |
| **DQ-RSN-01** | Reasonability | Fresh unit weight ($\sum$ 8 ingredients) | $2,100 \le \sum \text{ingredients} \le 2,600\text{ kg/m}^3$ | Normal/high-performance concrete density must obey physical mass-volume bounds. | Route to Quarantine |
| **DQ-RSN-02** | Reasonability | Water-to-binder ratio (`ratio_wb`) | $0.18 \le \text{water/total\_binder} \le 0.95$ | Ratios outside this range indicate unit conversion errors or unworkable/segregated mixes. | Route to Quarantine |
| **DQ-UNQ-01** | Uniqueness | Business key: `(source_id, 8 ingredients, age, compressive_strength)` | Only the first ingested occurrence is kept in Silver; exact duplicates are flagged. | Prevents duplicate rows from inflating sample weights or leaking across CV folds. | Keep first in Silver; route duplicates to Quarantine |
