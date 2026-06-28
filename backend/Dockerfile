FROM python:3.12-slim

WORKDIR /app

# Install Node.js (for web-push npm package) and Python dependencies
RUN apt-get update && apt-get install -y nodejs npm libreoffice-writer libreoffice-calc libreoffice-impress --no-install-recommends && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY package.json .
RUN npm install --omit=dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for token persistence
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
