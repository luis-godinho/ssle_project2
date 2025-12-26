#!/bin/bash

echo "🔐 Checking Vault Status"
echo "========================"
echo ""

if [ ! -f .vault/root-token ]; then
  echo "❌ Vault not initialized. Run: ./scripts/init-vault.sh"
  exit 1
fi

ROOT_TOKEN=$(cat .vault/root-token)

# Check Vault health
echo "📊 Vault Health:"
curl -s http://localhost:8200/v1/sys/health | jq '{initialized, sealed, standby}'
echo ""

# List BFT node tokens
echo "🔑 BFT Node Tokens:"
for NODE in order-node-1 order-node-2 order-node-3; do
  TOKEN=$(curl -s --header "X-Vault-Token: $ROOT_TOKEN" \
    http://localhost:8200/v1/secret/data/bft-cluster/$NODE | jq -r '.data.data.auth_token')
  echo "  $NODE: ${TOKEN:0:16}..."
done
echo ""

# List service tokens
echo "🔑 Service Tokens:"
for SERVICE in product-service payment-service email-service api-gateway; do
  TOKEN=$(curl -s --header "X-Vault-Token: $ROOT_TOKEN" \
    http://localhost:8200/v1/secret/data/services/$SERVICE | jq -r '.data.data.service_token')
  echo "  $SERVICE: ${TOKEN:0:16}..."
done
echo ""

# Registry token
echo "🔑 Registry Token:"
REG_TOKEN=$(curl -s --header "X-Vault-Token: $ROOT_TOKEN" \
  http://localhost:8200/v1/secret/data/registry/api-token | jq -r '.data.data.api_token')
echo "  Service Registry: ${REG_TOKEN:0:16}..."
echo ""

echo "✅ Vault is operational"
