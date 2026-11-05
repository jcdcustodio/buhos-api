# Base Docker image
FROM python:3.14.9-slim

# Copy the 'uv' and 'uvx' executables from the latest uv image into /bin/ in this image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory inside the container to /src
# All subsequent commands will be run from here
WORKDIR /src

# Add the virtual environment's bin directory to the PATH so Python tools work globally
ENV PATH="/src/.venv/bin:$PATH"

# Copy the project configuration files into the container
# Done first for better layer caching
COPY "./docker-cfg/pyproject.toml" "pyproject.toml"
COPY "./docker-cfg/uv.lock" "uv.lock"
COPY "./docker-cfg/.python-version" ".python-version"

# Install dependencies exactly as locked in uv.lock, without updating them
RUN uv sync --locked --no-install-project

# Copy application code and model data into the container
COPY "predict.py" "train_util.py" "csp_model.joblib" ./

# Expose TCP port so it can be accessed from outside the container
EXPOSE 1313

# Run the application using uvicorn
# predict:app -> refers to 'app' object inside predict.py
# --host 0.0.0.0 -> listen on all interfaces
# --port 1313    -> listen on port 1313
ENTRYPOINT ["uvicorn", "predict:app", "--host", "0.0.0.0", "--port", "1313"]