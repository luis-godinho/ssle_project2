#!/bin/bash
set -e

echo "🔐 Step 1: Initialize Vault"
docker-compose down -v
docker-compose up -d vault
sleep 15
./scripts/init-vault.sh

echo "📝 Step 2: Create .env file"
cat >.env <<EOF
VAULT_TOKEN=$(cat .vault/app-token)
VAULT_ADDR=http://vault:8200
EOF

echo "✅ .env created:"
cat .env

echo "🚀 Step 3: Start all services"
docker-compose up --build
