FROM python:3.12-slim

WORKDIR /app

# Install Node.js, LibreOffice and unoserver dependencies
RUN apt-get update && apt-get install -y nodejs npm libreoffice-writer libreoffice-calc libreoffice-impress --no-install-recommends && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY package.json .
RUN npm install --omit=dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir unoserver

# Copy application code
COPY . .

# Create data directory for token persistence
RUN mkdir -p /app/data

# Make startup script executable
RUN chmod +x /app/start.sh

# Expose port
EXPOSE 8000

CMD ["/app/start.sh"]
