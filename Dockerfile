FROM python:3.11-slim

# Set a working directory that won't be overridden
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip, setuptools, and wheel
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy dependencies and install them
COPY requirements.txt .
RUN pip install --no-cache-dir bibtexparser==1.4.0
RUN pip install --no-cache-dir -r requirements.txt

# Copy the script into /app (this directory is inside the image)
COPY check_retractions.py .

# (Optional) Debug step to list the contents of /app
RUN ls -la .

# Use the baked-in script
ENTRYPOINT ["python", "check_retractions.py"]
