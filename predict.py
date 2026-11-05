from typing import Literal

import joblib
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field, ConfigDict


# Request
class ConcreteSample(BaseModel):
    # Raise a validation error if any extra or unexpected fields are passed during initialization
    model_config = ConfigDict(extra="forbid")

    cement: float = Field(..., ge=0.0)
    blast_furnace_slag: float = Field(..., ge=0.0)
    fly_ash: float = Field(..., ge=0.0)
    silica_fume: float = Field(..., ge=0.0)
    coarse_aggregate: float = Field(..., ge=0.0)
    fine_aggregate: float = Field(..., ge=0.0)
    water: float = Field(..., ge=0.0)
    superplasticizer: float = Field(..., ge=0.0)
    age: int = Field(..., ge=0.0)


# Response
class PredictResponse(BaseModel):
    concrete_strength: float


app = FastAPI(title="buhos-api")

csp_model_pipeline = joblib.load("csp_model.joblib")

def predict_single(concrete_sample):
    """Predict concrete strength given a single input."""
    result = csp_model_pipeline.predict(concrete_sample)[0]
    return float(result)


@app.post("/predict")
def predict(concrete_sample: ConcreteSample) -> PredictResponse:
    result = predict_single(concrete_sample.model_dump())

    return PredictResponse(
        concrete_strength=result
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=1313)
