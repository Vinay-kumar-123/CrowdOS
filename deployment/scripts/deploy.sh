#!/usr/bin/env bash
set -e

echo "=== Deploying CrowdOS Enterprise Stack ==="
docker compose pull || true
docker compose build --parallel
docker compose up -d --remove-orphans
echo "=== Deployment Successful! ==="
