#!/bin/bash
set -e

echo "🚀 SSLE Project 2 Setup Script"
echo "=============================="
echo ""

# Create required directories
echo "📁 Creating directories..."
mkdir -p monitoring/prometheus
mkdir -p monitoring/grafana/provisioning/datasources
mkdir -p monitoring/grafana/provisioning/dashboards
mkdir -p monitoring/grafana/dashboards
mkdir -p monitoring/alertmanager
mkdir -p vault/policies
mkdir -p wazuh/config

echo "✅ Directories created"
echo ""

# Check if Docker is running
echo "🐳 Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi
echo "✅ Docker is running"
echo ""

# Build images
echo "🔨 Building Docker images..."
docker-compose build
echo "✅ Images built"
echo ""

# Start services
echo "🚀 Starting services..."
docker-compose up -d
echo "✅ Services started"
echo ""

# Wait for services
echo "⏳ Waiting for services to be healthy..."
sleep 10

echo ""
echo "✅ Setup complete!"
echo ""
echo "📊 Service URLs:"
echo "  - Web:        http://localhost"
echo "  - API Gateway: http://localhost:8080"
echo "  - Registry:    http://localhost:5000"
echo "  - Prometheus:  http://localhost:9090"
echo "  - Grafana:     http://localhost:3000 (admin/admin)"
echo "  - Vault:       http://localhost:8200 (token: root)"
echo ""
echo "📝 Check logs:"
echo "  docker-compose logs -f [service-name]"
echo ""
