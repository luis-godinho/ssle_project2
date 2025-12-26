# 🚀 Vault Integration - Quick Start

## 5-Minute Setup

### Prerequisites
- Docker & Docker Compose installed
- `jq` installed (for JSON parsing)
- `curl` installed

---

## Step 1: Clone and Checkout Branch

```bash
cd ssle_project2
git checkout vault-integration
```

---

## Step 2: Start Vault

```bash
# Start only Vault first
docker-compose -f docker-compose.vault.yml up -d vault

# Wait for Vault to be ready (about 5 seconds)
sleep 5
```

---

## Step 3: Initialize Vault

```bash
# Make scripts executable
chmod +x scripts/init-vault.sh scripts/check-vault.sh

# Initialize Vault and create secrets
./scripts/init-vault.sh
```

**Expected Output:**
```
🔐 Initializing Vault...
✅ Vault is ready
✅ Vault initialized
✅ Creating BFT node tokens... (3 tokens)
✅ Creating service tokens... (4 tokens)
🎉 Vault initialization complete!
```

---

## Step 4: Export Vault Token

```bash
# Export the application token for services
export VAULT_TOKEN=$(cat .vault/app-token)
export VAULT_ADDR=http://localhost:8200

echo "Vault token exported: ${VAULT_TOKEN:0:20}..."
```

---

## Step 5: Start All Services

```bash
# Start everything with Vault integration
docker-compose -f docker-compose.vault.yml up -d

# Wait for services to start
sleep 10
```

---

## Step 6: Verify Everything Works

### Check Vault Status
```bash
./scripts/check-vault.sh
```

**Expected Output:**
```
🔐 Checking Vault Status
📊 Vault Health:
{
  "initialized": true,
  "sealed": false,
  "standby": false
}

🔑 BFT Node Tokens:
  order-node-1: a1b2c3d4e5f6g7h8...
  order-node-2: i9j0k1l2m3n4o5p6...
  order-node-3: q7r8s9t0u1v2w3x4...

✅ Vault is operational
```

### Check Cluster Status
```bash
curl -s http://localhost:8002/consensus/status | jq
```

**Expected Output:**
```json
{
  "cluster_size": 3,
  "healthy_nodes": 3,
  "quorum_size": 2,
  "quorum_available": true,
  "vault_auth_enabled": true,
  "nodes": [
    {"node": "http://order-node-1:8002", "status": "healthy"},
    {"node": "http://order-node-2:8012", "status": "healthy"},
    {"node": "http://order-node-3:8022", "status": "healthy"}
  ]
}
```

✅ Look for **`"vault_auth_enabled": true`** - this confirms Vault is working!

---

## Step 7: Test Authenticated Votes

### Create an Order (Triggers BFT Consensus)
```bash
curl -X POST http://localhost:8002/api/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST001",
    "items": [
      {"product_id": "PROD001", "quantity": 2, "price": 999.99}
    ]
  }' | jq
```

**Expected Output:**
```json
{
  "order_id": "ORD-1735217824-order-node-1",
  "customer_id": "CUST001",
  "items": [...],
  "status": "pending",
  "total": 1999.98,
  "created_by": "order-node-1",
  "consensus_operation_id": "a1b2c3d4e5f6g7h8",
  "authenticated_votes": 3
}
```

✅ **`"authenticated_votes": 3`** means all 3 nodes signed their votes with Vault tokens!

---

## Step 8: View Logs to See Vault in Action

```bash
# See Vault authentication messages
docker logs order-node-1 2>&1 | grep -i "vault\|token\|signature"
```

**Expected Output:**
```
INFO - Node authentication token loaded from Vault for order-node-1
INFO - Vault authentication: enabled
INFO - Validating operation abc123 from order-node-2
DEBUG - Vote signature verified for order-node-2
```

---

## Step 9: Access Vault UI (Optional)

```bash
# Get your root token
cat .vault/root-token

# Open Vault UI
open http://localhost:8200/ui
# Or visit in browser: http://localhost:8200/ui
```

**Login:**
1. Method: Token
2. Token: (paste from `.vault/root-token`)
3. Sign In

**Browse Secrets:**
1. Click "secret/"
2. Browse:
   - `bft-cluster/order-node-1` - See BFT node token
   - `bft-cluster/order-node-2`
   - `bft-cluster/order-node-3`
   - `services/product-service` - Service tokens
   - `registry/api-token` - Registry master token

---

## 🧪 What to Test

### Test 1: All Nodes Healthy (3/3 Quorum)
```bash
# Create order - should succeed
curl -X POST http://localhost:8002/api/orders \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "TEST1", "items": [{"product_id": "P1", "quantity": 1}]}'

# Check: "authenticated_votes": 3 ✅
```

### Test 2: One Node Down (2/3 Quorum)
```bash
# Stop one node
docker stop order-node-3

# Create order - should still succeed
curl -X POST http://localhost:8002/api/orders \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "TEST2", "items": [{"product_id": "P2", "quantity": 1}]}'

# Check: "authenticated_votes": 2 ✅ (quorum still met)
```

### Test 3: Two Nodes Down (1/3 - No Quorum)
```bash
# Stop another node
docker stop order-node-2

# Create order - should fail
curl -X POST http://localhost:8002/api/orders \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "TEST3", "items": [{"product_id": "P3", "quantity": 1}]}'

# Error: "quorum not reached" ❌
```

### Test 4: Restart Nodes
```bash
# Restart stopped nodes
docker start order-node-2 order-node-3

# Wait for them to rejoin
sleep 5

# Verify cluster healthy
curl http://localhost:8002/consensus/status | jq '.healthy_nodes'
# Output: 3 ✅
```

---

## 📊 What Makes This Different?

### Without Vault (main branch):
```json
// Vote response
{
  "node": "order-node-2",
  "vote": "approve"
}
```
**Problem:** Anyone can fake this vote!

### With Vault (this branch):
```json
// Vote response
{
  "node": "order-node-2",
  "vote": "approve",
  "signature": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6..."
}
```
**Security:** Signature is HMAC-SHA256 of vote using node's secret token from Vault.

**Verification:**
```python
# Proposer verifies:
node2_token = vault_client.get_bft_node_token("order-node-2")
expected = hmac.new(node2_token, message, sha256).hexdigest()

if signature != expected:
    logger.error("BYZANTINE BEHAVIOR DETECTED")
    # Vote rejected ❌
```

---

## 🛠️ Troubleshooting

### Vault not initialized?
```bash
# Check if Vault is running
docker ps | grep vault

# Re-initialize
docker-compose -f docker-compose.vault.yml down -v
docker-compose -f docker-compose.vault.yml up -d vault
sleep 5
./scripts/init-vault.sh
```

### Services can't connect to Vault?
```bash
# Check VAULT_TOKEN is set
echo $VAULT_TOKEN

# Re-export if empty
export VAULT_TOKEN=$(cat .vault/app-token)

# Restart services
docker-compose -f docker-compose.vault.yml restart
```

### "vault_auth_enabled": false?
```bash
# Services didn't get Vault token
# Check environment
docker exec order-node-1 env | grep VAULT

# Should show:
# VAULT_ADDR=http://vault:8200
# VAULT_TOKEN=hvs.abc123...

# If missing, restart with token:
export VAULT_TOKEN=$(cat .vault/app-token)
docker-compose -f docker-compose.vault.yml up -d
```

---

## 📝 Files to Check

### Verify Vault Credentials
```bash
ls -la .vault/
# Should show:
# -rw------- 1 user user  44 Dec 26 12:00 unseal-key
# -rw------- 1 user user  95 Dec 26 12:00 root-token
# -rw------- 1 user user  95 Dec 26 12:00 app-token
```

### Check Logs
```bash
# Vault logs
docker logs vault

# Order service logs (should show Vault auth)
docker logs order-node-1 | head -20

# Look for:
# "Node authentication token loaded from Vault"
# "Vault authentication: enabled"
```

---

## 🏁 Success Criteria

✅ Vault UI accessible at http://localhost:8200/ui  
✅ `check-vault.sh` shows all tokens  
✅ Cluster status shows `"vault_auth_enabled": true`  
✅ Orders create with `"authenticated_votes": 3`  
✅ Logs show "Node authentication token loaded from Vault"  
✅ No Byzantine behavior errors (unless simulated)  

---

## 📦 Cleanup

```bash
# Stop everything
docker-compose -f docker-compose.vault.yml down

# Remove volumes (deletes Vault data)
docker-compose -f docker-compose.vault.yml down -v

# Remove credentials
rm -rf .vault/
```

---

## 📚 Next Steps

1. Read **[VAULT_INTEGRATION.md](./VAULT_INTEGRATION.md)** for detailed explanation
2. Try simulating Byzantine attacks
3. Explore Vault UI to see all secrets
4. Check Prometheus metrics for vote signatures
5. Review logs for authentication messages

---

## ❓ Questions?

**Q: Why use Vault instead of environment variables?**  
A: Vault provides centralized secret management, automatic rotation, audit logs, and access control.

**Q: Is this necessary for the project?**  
A: No, but it demonstrates production-grade security and prevents Byzantine vote spoofing.

**Q: Can I merge this to main?**  
A: Keep it separate! Use main for core BFT+MTD, this branch for advanced security demo.

**Q: What if Vault is down?**  
A: Services gracefully degrade - they work without authentication (logged as warning).

---

Good luck! 🚀
