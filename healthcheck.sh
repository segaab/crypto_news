#!/bin/bash

# Check if the service is responding
curl -f http://localhost:8000/articles || exit 1

# Check if Redis is running
docker exec rss_redis redis-cli ping || exit 1 