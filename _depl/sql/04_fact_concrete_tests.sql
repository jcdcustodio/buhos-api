CREATE OR REPLACE TABLE gold_cs.fact_concrete_tests AS
SELECT
    sample_id,
    md5(
        CAST(ROUND(cement, 2) AS VARCHAR) || '|' ||
        CAST(ROUND(blast_furnace_slag, 2) AS VARCHAR) || '|' ||
        CAST(ROUND(fly_ash, 2) AS VARCHAR) || '|' ||
        CAST(ROUND(silica_fume, 2) AS VARCHAR) || '|' ||
        CAST(ROUND(coarse_aggregate, 2) AS VARCHAR) || '|' ||
        CAST(ROUND(fine_aggregate, 2) AS VARCHAR) || '|' ||
        CAST(ROUND(water, 2) AS VARCHAR) || '|' ||
        CAST(ROUND(superplasticizer, 2) AS VARCHAR)
    ) AS mix_design_id,
    _source_id AS src,
    age AS age_days,
    ROUND(compressive_strength, 2) AS actual_strength_mpa,
    ROUND(predicted_strength, 2) AS predicted_strength_mpa,
    ROUND(compressive_strength - predicted_strength, 2) AS strength_residual_mpa,
    _source_file AS source_file,
    _raw_row_num AS raw_row_num,
    _ingested_at AS ingested_at
FROM temp_scored_valid_samples
;