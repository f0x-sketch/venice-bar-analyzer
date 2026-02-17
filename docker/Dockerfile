FROM python:3.11-slim

WORKDIR /app

# Install git (needed for populartimes) and gcc
RUN apt-get update && apt-get install -y git gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install populartimes from git (not available on PyPI)
RUN pip install git+https://github.com/m-wrz/populartimes.git

# Copy application
COPY src/ ./src/
COPY scripts/generate_csv.py ./generate_csv.py

# Create output directory
RUN mkdir -p /output

# Environment
ENV PYTHONPATH=/app/src
ENV OUTPUT_DIR=/output

# Run once and exit
CMD ["python", "generate_csv.py"]
