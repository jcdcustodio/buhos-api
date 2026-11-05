# Buhos (Concrete Compressive Strength Prediction)

## Directory Overview

```markdown
buhos-api/
├── data/                       # Formatted data in CSV
│   └── raw/                    # Raw data originally in XLSX
├── docker-cfg/                 # Project configuration for Docker image creation
├── service/                    # Directory for model deployment
├── images/                     # Documentation images
├── refcalcs/                   # Reference calculations for cross-checking predictions
├── nb_eda_fe.ipynb             # Notebook for EDA, feature engineering, and baseline modeling
├── nb_model_dev.ipynb          # Notebook for model training (including tuning and cross-validation)
├── nb_train_script.ipynb       # Notebook for packaging the model training as a script
├── csp_model.joblib            # Exported model file
├── pipeline_util.py            # Helper functions for the model pipeline
├── predict.py                  # Web service for the model
├── train.py                    # Script for model training
├── sample_predict.py           # Sample prediction by importing the model file
├── sample_request.py           # Sample prediction by using the web service
└── pyproject.toml              # Project environment configuration
```
