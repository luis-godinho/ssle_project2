#!/bin/bash
set -e

echo "🔐 Initializing Vault..."
echo ""

# Wait for Vault to be ready
echo "Waiting for Vault to start..."
until curl -s http://localhost:8200/v1/sys/health > /dev/null 2>&1; do
  echo -n "."
  sleep 2
done
echo ""
echo "✅ Vault is ready"

# Check if Vault is already initialized
INIT_STATUS=$(curl -s http://localhost:8200/v1/sys/init | jq -r '.initialized')

if [ "$INIT_STATUS" = "true" ]; then
  echo "⚠️  Vault is already initialized"
  echo ""
  echo "To re-initialize Vault:"
  echo "  1. docker-compose down -v"
  echo "  2. docker-compose up -d vault"
  echo "  3. ./scripts/init-vault.sh"
  exit 0
fi

echo "Initializing Vault with 1 key share (DEV MODE)..."

# Initialize Vault
INIT_OUTPUT=$(curl -s --request POST \
  --data '{"secret_shares": 1, "secret_threshold": 1}' \
  http://localhost:8200/v1/sys/init)

# Extract keys and token
UNSEAL_KEY=$(echo $INIT_OUTPUT | jq -r '.keys[0]')
ROOT_TOKEN=$(echo $INIT_OUTPUT | jq -r '.root_token')

echo "✅ Vault initialized"
echo ""

# Save credentials
mkdir -p .vault
echo $UNSEAL_KEY > .vault/unseal-key
echo $ROOT_TOKEN > .vault/root-token
chmod 600 .vault/*

echo "📝 Credentials saved to .vault/ directory"
echo "   Unseal Key: .vault/unseal-key"
echo "   Root Token: .vault/root-token"
echo ""

# Unseal Vault
echo "Unsealing Vault..."
curl -s --request POST \
  --data "{\"key\": \"$UNSEAL_KEY\"}" \
  http://localhost:8200/v1/sys/unseal > /dev/null

echo "✅ Vault unsealed"
echo ""

# Enable KV secrets engine
echo "Enabling KV v2 secrets engine..."
curl -s --request POST \
  --header "X-Vault-Token: $ROOT_TOKEN" \
  --data '{"type": "kv-v2"}' \
  http://localhost:8200/v1/sys/mounts/secret > /dev/null

echo "✅ KV secrets engine enabled"
echo ""

# Create BFT node authentication tokens
echo "Creating BFT node authentication tokens..."
for NODE in order-node-1 order-node-2 order-node-3; do
  TOKEN=$(openssl rand -hex 32)
  curl -s --request POST \
    --header "X-Vault-Token: $ROOT_TOKEN" \
    --data "{\"data\": {\"auth_token\": \"$TOKEN\"}}" \
    http://localhost:8200/v1/secret/data/bft-cluster/$NODE > /dev/null
  echo "  ✅ $NODE: token created"
done
echo ""

# Create Service Registry master token
echo "Creating Service Registry API token..."
REGISTRY_TOKEN=$(openssl rand -hex 32)
curl -s --request POST \
  --header "X-Vault-Token: $ROOT_TOKEN" \
  --data "{\"data\": {\"api_token\": \"$REGISTRY_TOKEN\"}}" \
  http://localhost:8200/v1/secret/data/registry/api-token > /dev/null
echo "  ✅ Service Registry: token created"
echo ""

# Create service authentication tokens
echo "Creating service authentication tokens..."
for SERVICE in product-service payment-service email-service api-gateway; do
  TOKEN=$(openssl rand -hex 32)
  curl -s --request POST \
    --header "X-Vault-Token: $ROOT_TOKEN" \
    --data "{\"data\": {\"service_token\": \"$TOKEN\"}}" \
    http://localhost:8200/v1/secret/data/services/$SERVICE > /dev/null
  echo "  ✅ $SERVICE: token created"
done
echo ""

# Create application policy for services
echo "Creating Vault policy for services..."
curl -s --request PUT \
  --header "X-Vault-Token: $ROOT_TOKEN" \
  --data @- http://localhost:8200/v1/sys/policies/acl/services-policy > /dev/null << EOF
{
  "policy": "path \"secret/data/services/*\" {\n  capabilities = [\"read\"]\n}\npath \"secret/data/bft-cluster/*\" {\n  capabilities = [\"read\"]\n}\npath \"secret/data/registry/*\" {\n  capabilities = [\"read\"]\n}"
}
EOF
echo "✅ Services policy created"
echo ""

# Create application token for services
echo "Creating application token for services..."
APP_TOKEN_RESPONSE=$(curl -s --request POST \
  --header "X-Vault-Token: $ROOT_TOKEN" \
  --data '{"policies": ["services-policy"], "ttl": "720h"}' \
  http://localhost:8200/v1/auth/token/create)

APP_TOKEN=$(echo $APP_TOKEN_RESPONSE | jq -r '.auth.client_token')
echo $APP_TOKEN > .vault/app-token
chmod 600 .vault/app-token

echo "✅ Application token created: .vault/app-token"
echo ""

echo "🎉 Vault initialization complete!"
echo ""
echo "📊 Summary:"
echo "   Vault URL: http://localhost:8200"
echo "   Root Token: $ROOT_TOKEN"
echo "   App Token: $APP_TOKEN"
echo ""
echo "🔑 Secrets created:"
echo "   - BFT node tokens: secret/bft-cluster/{order-node-1,order-node-2,order-node-3}"
echo "   - Registry token: secret/registry/api-token"
echo "   - Service tokens: secret/services/{product,payment,email,api-gateway}-service"
echo ""
echo "💡 Export app token for services:"
echo "   export VAULT_TOKEN=$APP_TOKEN"
echo "   export VAULT_ADDR=http://localhost:8200"
echo ""
echo "🌐 Access Vault UI:"
echo "   http://localhost:8200/ui"
echo "   Token: $ROOT_TOKEN"
echo ""
