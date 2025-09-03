#!/bin/bash

# setup.sh - Setup script for MinIO Telegram Bot

echo "Setting up MinIO Telegram Bot..."

# Create necessary directories
mkdir -p config temp logs

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check Docker Compose (try both v1 and v2 syntax)
DOCKER_COMPOSE_CMD=""
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
    echo "Found docker-compose (v1)"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
    echo "Found docker compose (v2)"
else
    echo "Docker Compose is not installed. Please install Docker Compose."
    echo ""
    echo "Installation options:"
    echo "1. Install Docker Desktop (includes Compose)"
    echo "2. Install docker-compose-plugin: sudo apt install docker-compose-plugin"
    echo "3. Manual install: https://docs.docker.com/compose/install/"
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file..."
    if [ -f .env.example ]; then
        cp .env.example .env
    else
        cat > .env << 'EOF'
# Telegram Bot Configuration
BOT_TOKEN=your_telegram_bot_token_here

# Google Sheets Configuration
SPREADSHEET_ID=your_google_spreadsheet_id_here
SERVICE_ACCOUNT_FILE=config/service_account.json

# Rate Limiting
RATE_LIMIT_SECONDS=2

# MinIO Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_BUCKET_NAME=telegram-bot-media
MINIO_SECURE=false
EOF
    fi
    echo "Please edit .env file with your configuration before running the bot."
fi

# Check if service account file exists
if [ ! -f config/service_account.json ]; then
    echo "Warning: config/service_account.json not found."
    echo "Please place your Google Service Account JSON file in the config directory."
fi

# Save the Docker Compose command for later use
echo "$DOCKER_COMPOSE_CMD" > .docker_compose_cmd

echo "Setup complete!"
echo ""
echo "Docker Compose command: $DOCKER_COMPOSE_CMD"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your bot token and other configuration"
echo "2. Place your Google Service Account JSON file in config/service_account.json"
echo "3. Run: ./manage.sh start"
echo "4. Access MinIO console at: http://localhost:9001"
echo "   Username: minioadmin"
echo "   Password: minioadmin123"