import numpy as np
import pandas as pd


def setup_format(X: pd.DataFrame | pd.Series | dict | list) -> pd.DataFrame:
    """Ensure model pipeline can accept multiple format."""

    # Wrap input to a list if a single dictionary or Series
    if isinstance(X, (dict, pd.Series)):
        X = [X]

    # Handles the following:
    # 1. An existing DataFrame (creates a copy)
    # 2. A list of dictionaries (creates a multi-row DataFrame)
    # 3. A list-wrapped dict/Series (creates a 1-row DataFrame)
    X_out = pd.DataFrame(X, copy=True)
    return X_out


def setup_features(X: pd.DataFrame) -> pd.DataFrame:
    """Handles feature engineering within the model pipeline."""

    # Remove irrelevant columns
    X_out = X.drop(columns=["sample_id", "src"], errors="ignore")

    # Scale age column into logarithmic values
    X_out["log_age"] = np.log1p(X_out["age"])
    X_out = X_out.drop(columns="age")

    # Derive relevant features
    scm_mats = ["blast_furnace_slag", "fly_ash", "silica_fume"]
    total_scm = X_out[scm_mats].sum(axis=1)
    total_binder = X_out["cement"] + total_scm
    ratio_wb = X_out["water"].div(total_binder)
    pct_scm_repl = total_scm.div(total_binder)

    # Clean inf and NaN safely before saving values
    X_out["ratio_wb"] = np.where(np.isfinite(ratio_wb), ratio_wb, 0.0)
    X_out["pct_scm_repl"] = np.where(np.isfinite(pct_scm_repl), pct_scm_repl, 0.0)

    return X_out