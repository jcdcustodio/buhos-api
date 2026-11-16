-- Exploded rule-level view across all quarantined concrete sample records
CREATE OR REPLACE VIEW gold_cs.sem_dq_quarantine_details AS
WITH exploded_failures AS (
    SELECT
        _source_id AS src,
        sample_id,
        _source_file AS source_file,
        _raw_row_num AS raw_row_num,
        failed_rule_count,
        TRIM(UNNEST(string_split(failed_rule_ids, ','))) AS rule_id,
        TRIM(UNNEST(CAST(CAST(failure_reasons AS JSON) AS VARCHAR[]))) AS failure_reason,
        _ingested_at AS quarantined_at
    FROM silver_cs.quarantine_samples
    WHERE failed_rule_count > 0
)
SELECT
    src,
    sample_id,
    source_file,
    raw_row_num,
    failed_rule_count,
    rule_id,
    CASE rule_id
        WHEN 'DQ-CMP-01' THEN 'Completeness'
        WHEN 'DQ-VAL-01' THEN 'Validity'
        WHEN 'DQ-VAL-02' THEN 'Validity'
        WHEN 'DQ-VAL-03' THEN 'Validity'
        WHEN 'DQ-CON-01' THEN 'Consistency'
        WHEN 'DQ-RSN-01' THEN 'Reasonability'
        WHEN 'DQ-RSN-02' THEN 'Reasonability'
        WHEN 'DQ-UNQ-01' THEN 'Uniqueness'
        ELSE 'Other'
    END AS dq_dimension,
    failure_reason,
    rule_id || ': ' || failure_reason AS failed_rule,
    quarantined_at
FROM exploded_failures
;

-- Run-level KPI summary view for top-level data quality scorecards
CREATE OR REPLACE VIEW gold_cs.sem_dq_run_summary AS
SELECT
    ROW_NUMBER() OVER (ORDER BY evaluated_at DESC) AS run_recency_rank,
    evaluated_at,
    total_evaluated,
    valid_count,
    quarantined_count,
    pass_rate_pct,
    failure_rate_pct
FROM silver_cs.data_quality_audit_logs
;