CREATE OR REPLACE TABLE gold_cs.dim_mix_design AS
WITH distinct_mixes AS (
    SELECT DISTINCT
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
        cement,
        blast_furnace_slag,
        fly_ash,
        silica_fume,
        coarse_aggregate,
        fine_aggregate,
        water,
        superplasticizer
    FROM silver_cs.valid_samples
)
SELECT
    mix_design_id,
    cement,
    blast_furnace_slag,
    fly_ash,
    silica_fume,
    coarse_aggregate,
    fine_aggregate,
    water,
    superplasticizer,
    ROUND(cement + blast_furnace_slag + fly_ash + silica_fume, 2) AS total_binder_kg_m3,
    ROUND(
        cement + blast_furnace_slag + fly_ash + silica_fume +
        coarse_aggregate + fine_aggregate + water + superplasticizer,
        2
    ) AS unit_weight_kg_m3,
    ROUND(
        water / (cement + blast_furnace_slag + fly_ash + silica_fume),
        4
    ) AS ratio_wb,
    ROUND(
        (blast_furnace_slag + fly_ash + silica_fume) /
        (cement + blast_furnace_slag + fly_ash + silica_fume),
        4
    ) AS pct_scm_repl,
    ROUND(
        superplasticizer /
        (cement + blast_furnace_slag + fly_ash + silica_fume),
        4
    ) AS pct_sp,
    ROUND(
        blast_furnace_slag /
        (cement + blast_furnace_slag + fly_ash + silica_fume),
        4
    ) AS pct_slag,
    ROUND(
        fly_ash /
        (cement + blast_furnace_slag + fly_ash + silica_fume),
        4
    ) AS pct_fly_ash,
    ROUND(
        silica_fume /
        (cement + blast_furnace_slag + fly_ash + silica_fume),
        4
    ) AS pct_silica_fume
FROM distinct_mixes
;