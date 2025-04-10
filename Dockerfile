FROM python:3.11-slim

WORKDIR /github/workspace

# System deps (keep minimal)
RUN apt-get update && apt-get install -y build-essential gcc && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install wheel
RUN pip install --upgrade pip setuptools wheel

# Install dependencies (split bibtexparser to pre-cache it)
COPY requirements.txt .
RUN pip install bibtexparser==1.4.0 && pip install -r requirements.txt

# Copy everything into container (repo contents)
COPY . .

# Ensure main script is executable
RUN chmod +x check_retractions.py

ENTRYPOINT ["python", "check_retractions.py"]

