CREATE OR REPLACE TABLE gold_cs.dim_source AS
SELECT DISTINCT
    _source_id AS src,
    CASE _source_id
        WHEN 'src1' THEN 'Concrete Compressive Strength Dataset (Yeh, 1998)'
        WHEN 'src2' THEN 'CICLAB-NTUST High Performance Concrete Dataset (2023)'
        ELSE 'External Plant / Lab Source (' || _source_id || ')'
    END AS source_description
FROM silver_cs.valid_samples
;