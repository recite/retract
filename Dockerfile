FROM python:3.11-slim

# Set GitHub Actions working directory
WORKDIR /github/workspace

# Install build tools and Python basics
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip setuptools wheel

# Preinstall bibtexparser to avoid wheel errors
COPY requirements.txt .
RUN pip install --no-cache-dir bibtexparser==1.4.0
RUN pip install --no-cache-dir -r requirements.txt

# Copy the script here (where GitHub will run the container)
COPY check_retractions.py .

ENTRYPOINT ["python", "check_retractions.py"]
