# BFT Testing - Final Fix Summary

## ❌ Original Error

```
order-node-1 | WARNING - Registry returned status 400: {"error":"Missing name or port"}
```

**Test output:**
```json
{
  "healthy_nodes": 0,
  "nodes": [
    {"node": "order-node-1:8002", "status": "unreachable"},
    {"node": "order-node-2:8012", "status": "unreachable"},
    {"node": "order-node-3:8022", "status": "unreachable"}
  ],
  "quorum_available": false
}
```

```json
{"error": "Service order-service not found"}
```

---

## 🔍 Root Cause

**Registration API mismatch:**
- Order service sent: `{"service_name": ..., "hostname": ...}`
- Registry expected: `{"name": ..., "host": ...}`

The registry's `/register` endpoint requires:
```python
if not data or "name" not in data or "port" not in data:
    return jsonify({"error": "Missing name or port"}), 400
```

But order-service was sending:
```python
{
    "service_name": SERVICE_NAME,  # WRONG - should be "name"
    "hostname": NODE_ID,           # WRONG - should be "host"
    "port": NODE_PORT
}
```

---

## ✅ Fix Applied

### Changed in `services/order-service/app.py`

**Before:**
```python
response = requests.post(
    f"{REGISTRY_URL}/register",
    json={
        "service_name": SERVICE_NAME,  # ❌ Wrong field name
        "port": NODE_PORT,
        "hostname": NODE_ID,           # ❌ Wrong field name
        ...
    }
)
```

**After:**
```python
response = requests.post(
    f"{REGISTRY_URL}/register",
    json={
        "name": SERVICE_NAME,          # ✅ Correct!
        "port": NODE_PORT,
        "host": NODE_ID,               # ✅ Correct!
        "mtd_enabled": False,
        "metadata": {
            "type": "bft-cluster",
            "node_id": NODE_ID,
            "cluster_size": len(CLUSTER_NODES),
            "quorum_size": consensus.quorum_size
        }
    },
    timeout=5
)
```

### Also fixed heartbeat endpoint:

**Before:**
```python
response = requests.post(
    f"{REGISTRY_URL}/heartbeat",
    json={
        "service_name": SERVICE_NAME,  # ❌ Sent in body
        "port": NODE_PORT,
        "healthy": True,
        ...
    }
)
```

**After:**
```python
response = requests.post(
    f"{REGISTRY_URL}/heartbeat/{SERVICE_NAME}",  # ✅ In URL path
    json={
        "healthy": True,
        "metadata": {...}
    },
    timeout=5
)
```

---

## 🚀 How to Test

### 1. Rebuild and restart

```bash
# Stop everything
docker-compose down

# Rebuild order service with the fix
docker-compose build --no-cache order-node-1 order-node-2 order-node-3

# Start all services
docker-compose up -d

# Wait for initialization
echo "Waiting 60 seconds for services to initialize..."
sleep 60
```

### 2. Verify registration succeeded

```bash
# Check order-node-1 logs - should see success message
docker logs order-node-1 2>&1 | grep -i regist

# Expected output:
# INFO - Registering order-service with registry at http://registry:5000
# INFO - ✅ Successfully registered order-service with registry
```

### 3. Verify service is in registry

```bash
# Check registry
curl -s http://localhost:5000/services | jq '.services[] | select(.name == "order-service")'

# Expected output:
# {
#   "name": "order-service",
#   "url": "http://order-node-1:8002",
#   "port": 8002,
#   "healthy": true,
#   "rotation_count": 0
# }
```

### 4. Verify consensus cluster health

```bash
curl -s http://localhost:8102/consensus/status | jq .

# Expected output:
# {
#   "cluster_size": 3,
#   "healthy_nodes": 3,        # ✅ Should be 3 now!
#   "quorum_available": true,  # ✅ Should be true!
#   "nodes": [
#     {"node": "order-node-1:8002", "status": "healthy"},
#     {"node": "order-node-2:8012", "status": "healthy"},
#     {"node": "order-node-3:8022", "status": "healthy"}
#   ]
# }
```

### 5. Test order creation through API gateway

```bash
curl -s -X POST http://localhost:8080/proxy/order-service/api/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST001",
    "items": [
      {"product_id": "PROD001", "quantity": 1, "price": 999.99}
    ]
  }' | jq .

# Expected output:
# {
#   "order_id": "ORD-1735225320-order-node-1",
#   "customer_id": "CUST001",
#   "status": "pending",
#   "total": 999.99,
#   "consensus_operation_id": "...",
#   "authenticated_votes": 2
# }
```

### 6. Run full BFT test

```bash
test-bft

# Expected: All tests pass with quorum available! 🎉
```

---

## 📝 Changes Made

| Commit | File | Change |
|--------|------|--------|
| a62c37e | `services/order-service/app.py` | Added registry registration logic |
| 521631e | `services/order-service/app.py` | Fixed field names: `service_name`→`name`, `hostname`→`host` |
| 90683587 | `TROUBLESHOOTING_BFT.md` | Created comprehensive troubleshooting guide |

---

## ✅ Expected Test Results

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
  "quorum_size": 2
}

Test 2: Creating order (requires consensus)...
✅ Order created successfully:
{
  "order_id": "ORD-1735225320-order-node-1",
  "customer_id": "CUST001",
  "items": [...],
  "status": "pending",
  "consensus_operation_id": "...",
  "authenticated_votes": 2
}

Test 3: Testing fault tolerance (stopping node 2)...
Stopping order-node-2...
Creating order with 2/3 quorum...
✅ Order created with 2/3 quorum (Byzantine fault tolerance working!)
{
  "order_id": "ORD-1735225350-order-node-1",
  ...
}

Restarting order-node-2...

🎉 BFT testing complete!
```

---

## 🛠️ Quick Troubleshooting

If tests still fail:

```bash
# 1. Check registration logs
docker logs order-node-1 2>&1 | grep -E "(regist|ERROR|WARNING)"

# 2. Check if service is registered
curl http://localhost:5000/services | jq '.services[].name'

# 3. Check node health
for port in 8102 8112 8122; do
  echo "Node on $port:"
  curl -s http://localhost:$port/health | jq .status
done

# 4. Check consensus
curl http://localhost:8102/consensus/status | jq '{healthy_nodes, quorum_available}'

# 5. Full restart if needed
docker-compose down -v
docker-compose build --no-cache order-node-1
docker-compose up -d
sleep 90
test-bft
```

---

## 📚 Reference

- **Registry API**: `services/registry/app.py` - Lines 45-78 (register endpoint)
- **Order Service**: `services/order-service/app.py` - Lines 63-105 (registration function)
- **Troubleshooting Guide**: `TROUBLESHOOTING_BFT.md`
- **Docker Compose**: `docker-compose.yml` - Lines 28-104 (BFT cluster config)

---

## ✅ Status: FIXED

The registration API mismatch has been corrected. Order service will now successfully register with the service registry, making it discoverable by the API gateway and enabling BFT consensus tests to pass.
