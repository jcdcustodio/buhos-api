# Data Dictionary

## Input features

1. `cement` - Quantity of Portland cement used in the sample's mix ($kg/m^3$)
2. `blast_furnace_slag` - Quantity of blast surface slag used in the sample's mix ($kg/m^3$)
3. `fly_ash` - Quantity of fly ash used in the sample's mix ($kg/m^3$)
4. `silica_fume` - Quantity of silica fume used in the sample's mix ($kg/m^3$)
5. `water` - Quantity of water used in the sample's mix ($kg/m^3$)
6. `superplasticizer` - Quantity of superplasticizer used in the sample's mix ($kg/m^3$)
7. `coarse_aggregate` - Quantity of coarse aggregate (e.g. gravel) used in the sample's mix ($kg/m^3$)
8. `fine_aggregate` - Quantity of fine aggregate (e.g. sand) used in the sample's mix ($kg/m^3$)
9. `age` - Curing age of sample (days)

## Derived features

These are automatically created within the model pipeline.

1. `log_age` - Curing age transformed into logarithmic scale
2. `ratio_wb` - Water-binder ratio, the ratio of the amount of water and the total amount of binding materials (cement and SCMs) in a mix
3. `pct_scm_repl` - Percentage of binding material replaced with SCMs, calculated as the ratio of the amount of SCMs and the total amount of binding materials

## Terms

- Supplementary Cementitious Materials (SCM) - Natural materials or industrial byproducts that are added or used as a partial replacement for Portland Cement in concrete mixtures. Examples include blast furnace slag, fly ash, and silica fume.
