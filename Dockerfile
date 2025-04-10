FROM python:3.11-slim

# Set working directory
WORKDIR /github/workspace

# System packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip & preinstall
RUN pip install --upgrade pip setuptools wheel
COPY requirements.txt .
RUN pip install --no-cache-dir bibtexparser==1.4.0
RUN pip install --no-cache-dir -r requirements.txt

# Copy the actual retraction check logic
COPY check_retractions.py /app/
ENTRYPOINT ["python", "/app/check_retractions.py"]

# Run it
ENTRYPOINT ["python", "check_retractions.py"]



