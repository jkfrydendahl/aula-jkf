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

# Startup script: launch unoserver (keeps LibreOffice warm), then uvicorn
RUN echo '#!/bin/bash\nunoserver --daemon --host 127.0.0.1 &\nsleep 3\nexec uvicorn app.main:app --host 0.0.0.0 --port 8000' > /app/start.sh && chmod +x /app/start.sh

# Expose port
EXPOSE 8000

CMD ["/app/start.sh"]
