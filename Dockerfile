FROM python:3.11-slim

# Use a directory not affected by the GitHub mount (which goes to /github/workspace)
WORKDIR /action

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip, setuptools, and wheel
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir bibtexparser==1.4.0
RUN pip install --no-cache-dir -r requirements.txt

# Copy your action code (check_retractions.py) into /action
COPY check_retractions.py .

# (Optional) Debug step: list the contents of /action
RUN ls -la /action

# Set an environment variable that tells your script where the consuming repo is mounted
# GitHub Actions mounts the consumer repo at /github/workspace
ENV SCAN_ROOT=/github/workspace

# Use an absolute path for the entrypoint so that it runs the baked-in script from /action
ENTRYPOINT ["python", "/action/check_retractions.py"]

