FROM python:3.11-slim

WORKDIR /app

# Install wheel first
RUN pip install --no-cache-dir wheel

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all repo files
COPY . .

# Run the script
ENTRYPOINT ["python", "check_retractions.py"]

