from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.metrics import mean_absolute_percentage_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

from pipeline_util import setup_features, setup_format

SEED = 13

# ############################
# 01 - LOAD AND TRANSFORM
# ############################

DATA_PATH = Path().cwd() / "data"
datasets = list(DATA_PATH.glob("data_src*.csv", case_sensitive=True))

columns = [
    "sample_id", 
    "src", 
    "cement", 
    "blast_furnace_slag", 
    "fly_ash", 
    "silica_fume", 
    "coarse_aggregate", 
    "fine_aggregate", 
    "water", 
    "superplasticizer", 
    "age", 
    "compressive_strength"
]

columns_fe = [
    "log_age",
    "ratio_wb",
    "pct_scm_repl"
]

features = columns[2:-2] + columns_fe
features_input = columns[2:-1]
target = "compressive_strength"


def wrangle_data(datasets: list[Path]) -> pd.DataFrame:
    frames = []
    for idx, file in enumerate(datasets):
        # Skip row containing the units of each column
        df_chunk = pd.read_csv(file, skiprows=[1])

        # Create unique ID and tag source
        df_chunk["sample_id"] = f"s{idx + 1}_" + (df_chunk.index + 1).astype(str)
        df_chunk["src"] = f"src{idx + 1}"

        frames.append(df_chunk)

    # Merge dataframes, fill null with zeroes, reorganize columns
    df = pd.concat(frames, ignore_index=True)
    df["silica_fume"] = df["silica_fume"].fillna(0)
    df = df.reindex(columns=columns)

    return df


# ############################
# 02 - TRAIN MODEL
# ############################

def predict(model, features_X, target_y, set_type):
    y_pred = model.predict(features_X)

    mae = mean_absolute_error(target_y, y_pred)
    rmse = root_mean_squared_error(target_y, y_pred)
    mape = mean_absolute_percentage_error(target_y, y_pred)
    r2, r2_adj = get_r2_scores(target_y, y_pred, list(features_X.columns))
    
    print(f"===== Scores - {set_type.upper()} =====")
    print(f"MAE: {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")
    print(f"MAPE: {mape:.4f}")
    print(f"R2: {r2:.4f}")
    print(f"R2 Adjusted: {r2_adj:.4f}")
    
    return y_pred


def get_metrics(model, features_X, target_y):
    y_pred = model.predict(features_X)
    
    mae = mean_absolute_error(target_y, y_pred)
    rmse = root_mean_squared_error(target_y, y_pred)
    mape = mean_absolute_percentage_error(target_y, y_pred)
    r2, r2_adj = get_r2_scores(target_y, y_pred, list(features_X.columns))

    return mae, rmse, mape, r2, r2_adj


def get_r2_scores(y_true, y_pred, features):
    r2 = r2_score(y_true, y_pred)
    
    n_samples = len(y_true)
    n_features = len(features)
    adj_r2 = 1 - (1 - r2) * (n_samples - 1) / (n_samples - n_features - 1)

    return r2, adj_r2


def train_model(df: pd.DataFrame) -> tuple[Pipeline, dict]:
    # Setup features matrix and target vector
    features_X = df[features_input]
    target_y = df[target]

    # Perform split
    X_full_train, X_test, y_full_train, y_test = train_test_split(
        features_X,
        target_y,
        test_size=0.2, 
        random_state=SEED
    )

    # Train model
    model_pipeline = Pipeline(steps=[
        ("setup_format", FunctionTransformer(setup_format, validate=False)),
        ("setup_features", FunctionTransformer(setup_features, validate=False)),
        ("model", xgb.XGBRegressor(
            n_estimators=300, 
            max_depth=4, 
            min_child_weight=2, 
            learning_rate=0.3, 
            random_state=SEED
        ))
    ])
    model_pipeline.fit(X_full_train, y_full_train)

    scores_test = get_metrics(
        model=model_pipeline,
        features_X=X_test,
        target_y=y_test
    )
    scores_test_dict = dict(zip(["mae", "rmse", "mape", "r2", "r2_adj"], scores_test))

    return model_pipeline, scores_test_dict


# ####################
# 03 - EXPORT MODEL
# ####################

def export_model(model: Pipeline, filename="csp_model"):
    file = f"{filename}.joblib"
    joblib.dump(model, file)
    print(f"Model file successfully saved to {Path(__file__).parent.resolve()}/{file}")


if __name__ == "__main__":
    # Load data
    df = wrangle_data(datasets=datasets)
    model_pipeline, scores = train_model(df)

    # print(scores)
    export_model(model_pipeline)
