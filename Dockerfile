FROM python:3.11-slim

# Explicitly set working directory
WORKDIR /github/workspace

# Install necessary tools
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip setuptools wheel

# Copy everything from current directory
COPY . .

# Debug: List contents of the directory
RUN ls -la

# Install dependencies
RUN pip install -r requirements.txt

# Ensure script is executable
RUN chmod +x check_retractions.py

# Debug: Show script contents
RUN head -n 5 check_retractions.py

# Run the script
ENTRYPOINT ["python", "check_retractions.py"]
