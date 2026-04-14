# Use the official Python slim image
FROM python:3.11-slim

# Set environment variables for Poetry and Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.8.2 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install "poetry==$POETRY_VERSION"

# Copy package config from root (since we need full dependencies)
COPY pyproject.toml poetry.lock* ./

# Install only production dependencies
RUN poetry install --no-root --only main

# Copy the rest of the application (including ui/ and reasoning_engine/ etc)
# Even though this is the UI container, it needs access to the same project structure for simplicity
COPY . .

# Expose Streamlit's default port
EXPOSE 8501

# Command to run the Streamlit app
CMD ["streamlit", "run", "ui/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
