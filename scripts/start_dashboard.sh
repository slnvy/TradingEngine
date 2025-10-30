#!/bin/bash

echo "starting monitoring stack..."

cd docker

if [ ! -f docker-compose.yml ]; then
    echo "error: docker-compose.yml not found in docker directory"
    exit 1
fi

docker-compose up -d

echo "monitoring stack started:"
echo "- grafana: http://localhost:3000 (admin/admin)"
echo "- prometheus: http://localhost:9090"
echo "- redis: localhost:6379"
echo ""
echo "to view logs: docker-compose logs -f"
echo "to stop: docker-compose down" 