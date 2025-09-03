#!/bin/bash

# manage.sh - Management script for MinIO Telegram Bot

# Determine Docker Compose command
if [ -f .docker_compose_cmd ]; then
    DOCKER_COMPOSE_CMD=$(cat .docker_compose_cmd)
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    echo "Docker Compose not found. Please run ./setup.sh first."
    exit 1
fi

case "$1" in
    "start")
        echo "Starting services..."
        $DOCKER_COMPOSE_CMD up -d
        echo "Services started!"
        echo "MinIO Console: http://localhost:9001"
        echo "Username: minioadmin"
        echo "Password: minioadmin123"
        ;;
    "stop")
        echo "Stopping services..."
        $DOCKER_COMPOSE_CMD down
        echo "Services stopped!"
        ;;
    "restart")
        echo "Restarting services..."
        $DOCKER_COMPOSE_CMD down
        $DOCKER_COMPOSE_CMD up -d
        echo "Services restarted!"
        ;;
    "logs")
        if [ -n "$2" ]; then
            echo "Showing logs for $2..."
            $DOCKER_COMPOSE_CMD logs -f "$2"
        else
            echo "Showing all logs..."
            $DOCKER_COMPOSE_CMD logs -f
        fi
        ;;
    "status")
        echo "Service status:"
        $DOCKER_COMPOSE_CMD ps
        ;;
    "build")
        echo "Building services..."
        $DOCKER_COMPOSE_CMD build
        echo "Build complete!"
        ;;
    "clean")
        echo "Cleaning up..."
        $DOCKER_COMPOSE_CMD down -v
        docker system prune -f
        echo "Cleanup complete!"
        ;;
    "backup")
        echo "Creating backup..."
        mkdir -p backups
        timestamp=$(date +"%Y%m%d_%H%M%S")

        # Backup MinIO data
        docker run --rm -v minio_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/minio_backup_${timestamp}.tar.gz -C /data .

        # Backup configuration
        cp -r config backups/config_backup_${timestamp}
        cp .env backups/env_backup_${timestamp}

        echo "Backup created: backups/*_${timestamp}"
        ;;
    "restore")
        if [ -z "$2" ]; then
            echo "Usage: $0 restore <backup_timestamp>"
            echo "Available backups:"
            ls -la backups/
            exit 1
        fi

        timestamp="$2"
        echo "Restoring from backup: $timestamp"

        # Stop services first
        $DOCKER_COMPOSE_CMD down

        # Restore MinIO data
        if [ -f "backups/minio_backup_${timestamp}.tar.gz" ]; then
            docker run --rm -v minio_data:/data -v $(pwd)/backups:/backup alpine sh -c "cd /data && tar xzf /backup/minio_backup_${timestamp}.tar.gz"
            echo "MinIO data restored"
        fi

        # Restore configuration
        if [ -d "backups/config_backup_${timestamp}" ]; then
            cp -r "backups/config_backup_${timestamp}" config
            echo "Configuration restored"
        fi

        if [ -f "backups/env_backup_${timestamp}" ]; then
            cp "backups/env_backup_${timestamp}" .env
            echo "Environment file restored"
        fi

        echo "Restore complete! Run '$0 start' to start services."
        ;;
    "shell")
        service="${2:-telegram-bot}"
        echo "Opening shell in $service container..."
        $DOCKER_COMPOSE_CMD exec "$service" /bin/bash
        ;;
    "update")
        echo "Updating services..."
        $DOCKER_COMPOSE_CMD pull
        $DOCKER_COMPOSE_CMD up -d
        echo "Update complete!"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|logs|status|build|clean|backup|restore|shell|update}"
        echo ""
        echo "Commands:"
        echo "  start    - Start all services"
        echo "  stop     - Stop all services"
        echo "  restart  - Restart all services"
        echo "  logs     - Show logs (optional: specify service name)"
        echo "  status   - Show service status"
        echo "  build    - Build Docker images"
        echo "  clean    - Clean up containers and volumes"
        echo "  backup   - Create backup of data and config"
        echo "  restore  - Restore from backup (requires timestamp)"
        echo "  shell    - Open shell in container (default: telegram-bot)"
        echo "  update   - Pull latest images and restart"
        echo ""
        echo "Examples:"
        echo "  $0 logs telegram-bot"
        echo "  $0 shell minio"
        echo "  $0 restore 20240101_120000"
        ;;
esac