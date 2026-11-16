CREATE OR REPLACE TABLE gold_cs.model_train_set AS
SELECT
    sample_id,
    _source_id AS src,
    cement,
    blast_furnace_slag,
    fly_ash,
    silica_fume,
    coarse_aggregate,
    fine_aggregate,
    water,
    superplasticizer,
    age,
    ROUND(compressive_strength, 2) AS compressive_strength
FROM silver_cs.valid_samples;