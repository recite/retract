FROM python:3.11-slim
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the script (updated path)
COPY .github/scripts/check_retractions.py .
ENTRYPOINT ["python", "check_retractions.py"]
