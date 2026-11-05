from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import joblib
import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict


# =========================================
# Path and artifact configuration
# =========================================

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "csp_model.joblib"

# Global dictionary or state container for runtime artifacts
ml_models: dict[str, Any] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Load models and resources on startup, clean up on shutdown.
    Avoids top-level execution crashes during testing or doc builds.
    """
    if MODEL_PATH.is_file():
        ml_models["model_pipeline"] = joblib.load(MODEL_PATH)
    else:
        # Allows server to boot even if artifact is missing in development/test
        ml_models["model_pipeline"] = None
        print(f"Warning: Model not found at {MODEL_PATH}")

    yield
    ml_models.clear()


# =========================================
# Initialize application
# =========================================

app = FastAPI(
    title="buhos-api",
    description="Web service for predicting concrete compressive strength using machine learning.",
    version="0.1.0",
    lifespan=lifespan,
)


# =========================================
# Define schemas
# =========================================

descriptions = {
    "cement": "Cement content - kg/m^3",
    "blast_furnace_slag": "Blast furnace slag added into mix - kg/m^3",
    "fly_ash": "Fly ash added into mix - kg/m^3",
    "silica_fume": "Silica fume added into mix - kg/m^3",
    "coarse_aggregate": "Coarse aggregate added to mix - kg/m^3",
    "fine_aggregate": "Fine aggregate added to mix - kg/m^3",
    "water": "Water added into mix - kg/m^3",
    "superplasticizer": "Superplasticizer added into mix - kg/m^3",
    "age": "Age of concrete - days",
    "concrete_strength": "Predicted concrete compressive strength - MPa"
}

class ConcreteSample(BaseModel):
    # Raise a validation error if any extra or unexpected fields are passed during initialization
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "cement": 540.0,
                "blast_furnace_slag": 0.0,
                "fly_ash": 0.0,
                "silica_fume": 0.0,
                "water": 162.0,
                "superplasticizer": 2.5,
                "coarse_aggregate": 1040.0,
                "fine_aggregate": 676.0,
                "age": 28,
            }
        }
    )

    cement: float = Field(..., ge=0.0, description=descriptions["cement"])
    blast_furnace_slag: float = Field(..., ge=0.0, description=descriptions["blast_furnace_slag"])
    fly_ash: float = Field(..., ge=0.0, description=descriptions["fly_ash"])
    silica_fume: float = Field(..., ge=0.0, description=descriptions["silica_fume"])
    coarse_aggregate: float = Field(..., ge=0.0, description=descriptions["coarse_aggregate"])
    fine_aggregate: float = Field(..., ge=0.0, description=descriptions["fine_aggregate"])
    water: float = Field(..., ge=0.0, description=descriptions["water"])
    superplasticizer: float = Field(..., ge=0.0, description=descriptions["superplasticizer"])
    age: int = Field(..., ge=0, description=descriptions["age"])


class PredictResponse(BaseModel):
    concrete_strength: float = Field(..., description=descriptions["concrete_strength"])


class HealthResponse(BaseModel):
    status: str
    is_model_loaded: bool


# =========================================
# Helper functions for inferencing
# =========================================

def predict_single(input_sample: dict) -> float:
    """Run model inference on a single sample."""
    csp_model_pipeline = ml_models.get("model_pipeline")
    if csp_model_pipeline is None:
        raise RuntimeError("Model pipeline is not loaded or missing.")

    result_pred = csp_model_pipeline.predict(input_sample)[0]
    return float(result_pred)


# =========================================
# API endpoints
# =========================================

@app.get(
    "/health", 
    response_model=HealthResponse, 
    tags=["Diagnostics"]
)
def health_check():
    """Health probe to confirm server status and model readiness."""
    is_loaded = ml_models.get("model_pipeline") is not None
    return HealthResponse(
        status="ok" if is_loaded else "degraded",
        is_model_loaded=is_loaded,
    )


@app.post(
    "/predict",
    response_model=PredictResponse,
    status_code=status.HTTP_200_OK,
    tags=["Inference"],
)
def predict(concrete_sample: ConcreteSample) -> PredictResponse:
    """Predict concrete compressive strength given composition and curing days."""
    try:
        prediction_val = predict_single(concrete_sample.model_dump())
        return PredictResponse(concrete_strength=prediction_val)
    except RuntimeError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(err),
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Inference error: {err!s}",
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=1313)
