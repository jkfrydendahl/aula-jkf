#!/bin/bash
set -e

# Start unoserver (keeps LibreOffice warm for fast conversions)
unoserver --executable /usr/bin/libreoffice &
UNOSERVER_PID=$!
echo "unoserver started (PID $UNOSERVER_PID)"

# Wait for unoserver to be ready
sleep 4

# Start the FastAPI app
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
