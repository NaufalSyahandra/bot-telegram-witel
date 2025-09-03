FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p config temp

# Set permissions
RUN chmod +x main.py

# Expose port (if needed for health checks)
EXPOSE 8080

# Run the bot
CMD ["python", "main.py"]