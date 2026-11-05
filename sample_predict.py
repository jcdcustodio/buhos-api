from pathlib import Path
import joblib


model_path = Path(__file__).resolve().parent / "csp_model.joblib"
csp_model_pipeline = joblib.load(model_path)

test_input = {
    "cement": 402,
    "blast_furnace_slag": 0,
    "fly_ash": 0,
    "silica_fume": 0,
    "coarse_aggregate": 992,
    "fine_aggregate": 732,
    "water": 205,
    "superplasticizer": 0,
    "age": 28
}

# Note that it returns an array by default
result = csp_model_pipeline.predict(test_input)
print(result, type(result))

# Extract value for single input
result = csp_model_pipeline.predict(test_input)[0]
print(result, type(result))