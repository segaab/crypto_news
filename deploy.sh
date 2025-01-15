#!/bin/bash

# Stop any running containers
docker-compose down

# Remove old containers, networks, and volumes
docker-compose rm -f

# Pull latest changes (if using git)
git pull

# Build the new images
docker-compose build --no-cache

# Start the services
docker-compose up -d

# Show running containers
docker-compose ps

# Show logs
docker-compose logs -f 