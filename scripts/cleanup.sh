#!/bin/bash

echo "🧹 Cleaning up SSLE Project 2..."
echo "================================"
echo ""

read -p "This will stop and remove all containers, volumes, and networks. Continue? (y/N): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo "🛑 Stopping containers..."
docker-compose down

read -p "Remove volumes (this deletes all data)? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️  Removing volumes..."
    docker-compose down -v
    echo "✅ Volumes removed"
fi

read -p "Remove images? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️  Removing images..."
    docker-compose down --rmi all
    echo "✅ Images removed"
fi

echo ""
echo "✅ Cleanup complete!"
