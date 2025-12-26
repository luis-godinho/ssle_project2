# BFT Testing Troubleshooting Guide

## Problem: "Service order-service not found" and "unreachable" nodes

### Root Causes

1. **Order service not registering** with the service registry
2. **Container network connectivity issues** between nodes
3. **Services not fully started** before tests run

---

## ✅ Solution Applied

The order-service app.py has been updated to:
- Auto-register with the service registry on startup
- Send periodic heartbeats to maintain registration
- Only the primary node (order-node-1) registers as "order-service"

---

## Step-by-Step Testing Process

### 1. Clean Start

```bash
# Stop everything and clean up
docker-compose down -v

# Remove old images to ensure rebuild
docker-compose build --no-cache order-node-1 order-node-2 order-node-3

# Start services
docker-compose up -d
```

### 2. Wait for Services to Initialize

**CRITICAL**: Don't run tests immediately! Services need time to:
- Build and start containers
- Connect to Vault
- Register with service registry
- Establish BFT cluster connections

```bash
# Wait at least 60 seconds
echo "Waiting for services to initialize..."
sleep 60
```

### 3. Verify Service Registry

```bash
# Check if order-service is registered
curl -s http://localhost:5000/services | jq '.services[] | select(.name == "order-service")'

# Expected output:
# {
#   "name": "order-service",
#   "port": 8002,
#   "hostname": "order-node-1",
#   "healthy": true,
#   "metadata": {
#     "type": "bft-cluster",
#     ...
#   }
# }
```

If you don't see the service:
```bash
# Check order-node-1 logs for registration errors
docker logs order-node-1 | grep -i "regist"

# Check if registry is running
docker logs service-registry
```

### 4. Verify BFT Nodes are Running

```bash
# Check all three nodes
for port in 8102 8112 8122; do
  echo "Testing node on port $port:"
  curl -s http://localhost:$port/health | jq .
done
```

**Expected**: Each node should return `{"status": "healthy", ...}`

### 5. Verify Internal Node Communication

```bash
# Check consensus status (tests internal communication)
curl -s http://localhost:8102/consensus/status | jq .

# Expected output:
# {
#   "cluster_size": 3,
#   "healthy_nodes": 3,  <-- Should be 3!
#   "quorum_available": true,  <-- Should be true!
#   "nodes": [
#     {"node": "order-node-1:8002", "status": "healthy"},
#     {"node": "order-node-2:8012", "status": "healthy"},
#     {"node": "order-node-3:8022", "status": "healthy"}
#   ]
# }
```

**If nodes show "unreachable"**:
```bash
# Check Docker network
docker network inspect ssle_project2_ecommerce-network | jq '.[0].Containers'

# Verify nodes can ping each other
docker exec order-node-1 ping -c 2 order-node-2
docker exec order-node-2 ping -c 2 order-node-3
```

### 6. Test API Gateway Routing

```bash
# Test if API gateway can find order-service
curl -s http://localhost:8080/proxy/order-service/health | jq .

# If it fails, check API gateway logs
docker logs api-gateway | tail -20
```

### 7. Run BFT Test

Only after all above checks pass:

```bash
# Using nix flake
test-bft

# OR direct script
./scripts/test-bft.sh
```

---

## Common Issues & Fixes

### Issue 1: "Service order-service not found"

**Cause**: Order service didn't register with registry

**Fix**:
```bash
# Check if order-node-1 started successfully
docker logs order-node-1 | grep -E "(ERROR|regist|starting)"

# If registration failed, restart order-node-1
docker-compose restart order-node-1

# Wait and check again
sleep 30
curl -s http://localhost:5000/services | jq '.services[].name'
```

### Issue 2: "healthy_nodes": 0, all nodes "unreachable"

**Cause**: Docker network issue or consensus.py bug

**Fix**:
```bash
# Check consensus.py for network calls
docker logs order-node-1 | grep -i "cluster\|consensus"

# Verify CLUSTER_NODES environment variable
docker exec order-node-1 env | grep CLUSTER

# Should show: CLUSTER_NODES=order-node-1:8002,order-node-2:8012,order-node-3:8022

# Test if nodes can reach each other on internal ports
docker exec order-node-1 curl -s http://order-node-2:8012/health
docker exec order-node-2 curl -s http://order-node-3:8022/health
```

### Issue 3: "quorum_available": false

**Cause**: Less than 2 nodes are healthy

**Fix**:
```bash
# Find which node(s) are down
curl -s http://localhost:8102/consensus/status | jq '.nodes'

# Check logs for the unhealthy nodes
docker logs order-node-2 | tail -50
docker logs order-node-3 | tail -50

# Common causes:
# - Vault connection failed
# - Registry unreachable
# - Python error in app.py or consensus.py
```

### Issue 4: Vault Authentication Errors

**Cause**: Vault not initialized or tokens missing

**Fix**:
```bash
# Check if Vault is ready
curl -s http://localhost:8200/v1/sys/health | jq .

# Initialize Vault if needed
./scripts/init-vault.sh

# Verify tokens were created
ls -la .vault/

# Restart order nodes to pick up Vault tokens
docker-compose restart order-node-1 order-node-2 order-node-3
```

### Issue 5: Port Conflicts

**Cause**: External ports (8102, 8112, 8122) already in use

**Fix**:
```bash
# Check what's using the ports
lsof -i :8102
lsof -i :8112  
lsof -i :8122

# If docker containers from previous run:
docker ps -a | grep order-node
docker rm -f order-node-1 order-node-2 order-node-3

# Restart cleanly
docker-compose up -d order-node-1 order-node-2 order-node-3
```

---

## Debug Checklist

Before running tests, verify:

- [ ] All containers running: `docker-compose ps`
- [ ] Registry accessible: `curl http://localhost:5000/services`
- [ ] Order-service registered: `curl http://localhost:5000/services | grep order-service`
- [ ] Node 1 healthy: `curl http://localhost:8102/health`
- [ ] Node 2 healthy: `curl http://localhost:8112/health`
- [ ] Node 3 healthy: `curl http://localhost:8122/health`
- [ ] Consensus status good: `curl http://localhost:8102/consensus/status | jq .quorum_available`
- [ ] API gateway routing works: `curl http://localhost:8080/proxy/order-service/health`
- [ ] Waited 60+ seconds after `docker-compose up -d`

---

## Complete Test Procedure

```bash
#!/bin/bash
set -e

echo "🧹 Step 1: Clean environment"
docker-compose down -v

echo "🔨 Step 2: Rebuild order service"
docker-compose build --no-cache order-node-1

echo "🚀 Step 3: Start all services"
docker-compose up -d

echo "⏳ Step 4: Wait for initialization (90 seconds)"
sleep 90

echo "✅ Step 5: Verify registry"
curl -sf http://localhost:5000/services | jq '.services[] | select(.name == "order-service")' || {
  echo "❌ Order service not registered!"
  docker logs order-node-1 | tail -20
  exit 1
}

echo "✅ Step 6: Verify consensus"
STATUS=$(curl -sf http://localhost:8102/consensus/status)
QUORUM=$(echo "$STATUS" | jq -r '.quorum_available')
if [ "$QUORUM" != "true" ]; then
  echo "❌ Quorum not available!"
  echo "$STATUS" | jq .
  exit 1
fi

echo "✅ Step 7: Run BFT tests"
test-bft

echo "🎉 All tests passed!"
```

Save as `test-bft-full.sh`, make executable, and run:
```bash
chmod +x test-bft-full.sh
./test-bft-full.sh
```

---

## Still Having Issues?

1. **Check all logs**: `docker-compose logs > all-logs.txt`
2. **Verify docker-compose.yml** has correct CLUSTER_NODES format
3. **Ensure app.py** has the updated registration code
4. **Test network connectivity** between containers
5. **Restart from scratch** with `docker-compose down -v && docker-compose up -d`

---

## Expected Successful Test Output

```
🧪 Testing Byzantine Fault Tolerance...

Test 1: Checking BFT cluster quorum...
✅ Cluster status:
{
  "cluster_size": 3,
  "healthy_nodes": 3,
  "nodes": [
    {"node": "order-node-1:8002", "status": "healthy"},
    {"node": "order-node-2:8012", "status": "healthy"},
    {"node": "order-node-3:8022", "status": "healthy"}
  ],
  "quorum_available": true,
  "quorum_size": 2,
  "vault_auth_enabled": false
}

Test 2: Creating order (requires consensus)...
✅ Order created successfully:
{
  "order_id": "ORD-1703601234-order-node-1",
  "customer_id": "CUST001",
  "status": "pending",
  "consensus_operation_id": "...",
  "authenticated_votes": 2
}

Test 3: Testing fault tolerance (stopping node 2)...
Stopping order-node-2...
✅ Order created with 2/3 quorum (Byzantine fault tolerance working!)

🎉 BFT testing complete!
```
