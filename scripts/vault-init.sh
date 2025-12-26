#!/bin/bash
set -e

echo "🔐 Initializing Vault with BFT Secrets"
echo "======================================"
echo ""

VAULT_ADDR="http://localhost:8200"
VAULT_TOKEN="root"

export VAULT_ADDR
export VAULT_TOKEN

echo "⏳ Waiting for Vault to be ready..."
until vault status > /dev/null 2>&1; do
    sleep 2
done
echo "✅ Vault is ready"
echo ""

# Enable KV secrets engine
echo "📝 Enabling KV secrets engine..."
vault secrets enable -path=secret kv-v2 2>/dev/null || echo "KV engine already enabled"
echo ""

# Store BFT node tokens
echo "🔑 Storing BFT node authentication tokens..."
vault kv put secret/bft-cluster/order-node-1 auth_token="node1-secret-token-$(openssl rand -hex 16)"
vault kv put secret/bft-cluster/order-node-2 auth_token="node2-secret-token-$(openssl rand -hex 16)"
vault kv put secret/bft-cluster/order-node-3 auth_token="node3-secret-token-$(openssl rand -hex 16)"
echo ""

# Store service tokens
echo "🔑 Storing service tokens..."
vault kv put secret/services/product-service service_token="product-$(openssl rand -hex 16)"
vault kv put secret/services/payment-service service_token="payment-$(openssl rand -hex 16)"
vault kv put secret/services/email-service service_token="email-$(openssl rand -hex 16)"
echo ""

# Store registry token
echo "🔑 Storing registry API token..."
vault kv put secret/registry/api-token api_token="registry-$(openssl rand -hex 16)"
echo ""

echo "✅ Vault initialization complete!"
echo ""
echo "📖 View secrets:"
echo "  vault kv get secret/bft-cluster/order-node-1"
echo "  vault kv get secret/services/product-service"
echo ""
