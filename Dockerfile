FROM python:3.11-slim

WORKDIR /app

# Add build dependencies for compiling packages
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install pip wheel explicitly (fix for bdist_wheel missing)
RUN pip install --upgrade pip wheel setuptools

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your source code
COPY . .

# Set entrypoint
ENTRYPOINT ["python", "check_retractions.py"]


