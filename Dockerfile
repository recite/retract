FROM python:3.11-slim

# Set working directory early to leverage Docker caching
WORKDIR /app

# Install system packages only if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip, setuptools, wheel (wheel is critical for fast builds)
RUN pip install --upgrade pip setuptools wheel

# Copy and install dependencies separately to leverage layer caching
COPY requirements.txt .

# Pre-install problematic packages first to cache their wheels
RUN pip install --no-cache-dir bibtexparser==1.4.0

# Install the rest (this way, only the fast-to-install packages rerun on changes)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the script only after dependencies are installed (faster rebuilds)
COPY check_retractions.py .

# Set default execution
ENTRYPOINT ["python", "check_retractions.py"]



