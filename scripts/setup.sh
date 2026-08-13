#!/usr/bin/env bash

# Exit immediately on error
set -e

echo "=== CrowdOS Project Initialization Setup ==="

# Check requirements
command -v node >/dev/null 2>&1 || { echo >&2 "Node.js is required but not installed. Aborting."; exit 1; }
command -v pnpm >/dev/null 2>&1 || { echo >&2 "pnpm is required but not installed. Aborting."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo >&2 "Python 3 is required but not installed. Aborting."; exit 1; }

# Setup environment files
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

if [ ! -f frontend/.env ]; then
    echo "Creating frontend/.env from frontend/.env.example..."
    cp frontend/.env.example frontend/.env
fi

if [ ! -f backend/.env ]; then
    echo "Creating backend/.env from backend/.env.example..."
    cp backend/.env.example backend/.env
fi

if [ ! -f ai-engine/.env ]; then
    echo "Creating ai-engine/.env from ai-engine/.env.example..."
    cp ai-engine/.env.example ai-engine/.env
fi

echo "=== Setup complete! ==="
