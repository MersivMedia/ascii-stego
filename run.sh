#!/bin/bash
# Run ASCII Stego web app

cd "$(dirname "$0")"

# Kill any existing instance
pkill -f "python3 app.py" 2>/dev/null || true

# Run with nohup for persistence
nohup python3 app.py > stego.log 2>&1 &

echo "ASCII Stego running on http://$(hostname -I | awk '{print $1}'):5050"
echo "Logs: $(pwd)/stego.log"
