#!/bin/bash

# Counselor Project Startup Script for Ubuntu/Linux
# This script activates the virtual environment and starts the Django development server

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Start Docker MySQL service first
echo "========================================="
echo "Starting Docker MySQL Service"
echo "========================================="
cd /home/itpc6/Public/0innerdb
echo "Stopping existing containers..."
docker-compose -f docker-compose-mysql.yaml down

echo "Starting MySQL container..."
docker-compose -f docker-compose-mysql.yaml up --build -d

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to start Docker MySQL service!"
    exit 1
fi

echo "✓ Docker MySQL service started"
echo "Waiting 5 seconds for MySQL to be ready..."
sleep 5
echo ""
