# Use the official Python slim image for a lightweight footprint
FROM python:3.11-slim

# Set environment variables to prevent Python from buffering stdout/stderr (good for Cloud Logging)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.8.2 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

# Install system dependencies if required for graphing libraries
RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

# Copy ONLY requirements first to cache the docker layer
COPY requirements.txt ./

# Install dependencies directly using pip (High Reliability Mode)
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the application code
COPY . .

# Expose Cloud Run's required port (8080) for the FastAPI Server
EXPOSE 8080

# Run Uvicorn securely on 0.0.0.0 so Cloud Run can dynamically route REST network traffic to it
ENV PORT=8080
CMD exec uvicorn api.main:app --host 0.0.0.0 --port $PORT
