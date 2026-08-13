#!/usr/bin/env bash
set -e

echo "Checking CrowdOS Services Health..."

curl -sf http://localhost:8000/health > /dev/null && echo "Backend: HEALTHY" || echo "Backend: UNHEALTHY"
curl -sf http://localhost:8001/health > /dev/null && echo "AI Engine: HEALTHY" || echo "AI Engine: UNHEALTHY"
curl -sf http://localhost:3000 > /dev/null && echo "Frontend: HEALTHY" || echo "Frontend: UNHEALTHY"
