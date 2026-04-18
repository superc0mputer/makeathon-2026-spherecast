FROM python:3.10-slim

# Prevent python from producing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies including Node.js
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    sqlite3 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy python requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Install frontend dependencies and build
WORKDIR /app/frontend/agnes-ui
RUN npm install && npm run build

# Expose the Next.js port
EXPOSE 3000

# Start the Next.js UI
CMD ["npm", "start"]
