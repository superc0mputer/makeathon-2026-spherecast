#!/usr/bin/env bash
set -e

echo "🐳 Building Docker image for Full Stack UI & Pipeline..."
docker build -t makeathon-pipeline .

echo "🚀 Starting the Next.js Dashboard inside Docker..."
echo "🔗 Access it at: http://localhost:3000"

# Map the local db directory to keep the sqlite db state updated
# Expose port 3000
# Load .env automatically
if [ -f .env ]; then
    docker run -it --rm \
        -p 3000:3000 \
        -v "$(pwd)/db:/app/db" \
        --env-file .env \
        makeathon-pipeline
else
    echo "⚠️ Warning: No .env file found. API limits or authentication may fail!"
    docker run -it --rm \
        -p 3000:3000 \
        -v "$(pwd)/db:/app/db" \
        makeathon-pipeline
fi

echo "✅ Finished running inside Docker."
