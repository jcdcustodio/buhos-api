CREATE OR REPLACE TABLE gold_cs.sem_analytics_qc AS
SELECT
    f.sample_id,
    f.mix_design_id,
    f.src,
    s.source_description,
    m.cement,
    m.blast_furnace_slag,
    m.fly_ash,
    m.silica_fume,
    m.coarse_aggregate,
    m.fine_aggregate,
    m.water,
    m.superplasticizer,
    m.total_binder_kg_m3,
    m.unit_weight_kg_m3,
    m.ratio_wb,
    m.pct_scm_repl,
    f.age_days,
    f.actual_strength_mpa,
    f.predicted_strength_mpa,
    f.strength_residual_mpa,
    -- Moving average of 3 consecutive tests per source & curing age (ACI 318)
    ROUND(
        AVG(f.actual_strength_mpa) OVER (
            PARTITION BY f.src, f.age_days
            ORDER BY f.source_file, f.raw_row_num
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ),
        2
    ) AS moving_avg_3_mpa,
    -- Rolling 30-test sample standard deviation per source & curing age (ACI 214R)
    ROUND(
        STDDEV_SAMP(f.actual_strength_mpa) OVER (
            PARTITION BY f.src, f.age_days
            ORDER BY f.source_file, f.raw_row_num
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ),
        2
    ) AS rolling_std_30_mpa,
    -- Cumulative Sum (CUSUM) of model residuals to detect process drift
    ROUND(
        SUM(f.strength_residual_mpa) OVER (
            PARTITION BY f.src, f.age_days
            ORDER BY f.source_file, f.raw_row_num
            ROWS UNBOUNDED PRECEDING
        ),
        2
    ) AS cusum_residual_mpa
FROM gold_cs.fact_concrete_tests f
JOIN gold_cs.dim_mix_design m USING (mix_design_id)
JOIN gold_cs.dim_source s USING (src)
;