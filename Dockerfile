FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all repo files into container
COPY . .

# Run the script
ENTRYPOINT ["python", "check_retractions.py"]
