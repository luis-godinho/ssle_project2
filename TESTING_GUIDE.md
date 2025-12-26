# Testing Guide - SSLE Project 2

## 🚀 Quick Start with Nix Flakes

### Prerequisites

Ensure you have Nix with flakes enabled:

```bash
# Check if Nix is installed
nix --version

# Enable flakes (add to ~/.config/nix/nix.conf or /etc/nix/nix.conf)
experimental-features = nix-command flakes
```

### Enter Development Environment

```bash
# Clone the repository
git clone https://github.com/luis-godinho/ssle_project2.git
cd ssle_project2

# Enter Nix development shell
nix develop

# You'll see:
# 🛡️  SSLE Project 2 - Attack Tolerance Mechanisms
# =================================================
# 
# 📚 Available commands:
#   start-project    - Start all Docker containers
#   stop-project     - Stop all containers
#   check-cluster    - Check cluster health
#   test-bft         - Test Byzantine Fault Tolerance
#   test-mtd         - Test Moving Target Defense
#   run-tests        - Run full test suite
```

---

## 📋 Testing Workflow

### Step 1: Start the Project

```bash
# Inside nix develop shell
start-project

# This will:
# ✅ Start all Docker containers
# ✅ Wait for services to initialize
# ✅ Show cluster health check
```

**Expected output:**
```
🚀 Starting SSLE Project 2...

📦 Starting containers...
Creating network "ecommerce-network" ... done
Creating service-registry ... done
Creating order-node-1 ... done
Creating order-node-2 ... done
Creating order-node-3 ... done
...

⏳ Waiting for services to initialize (30s)...

📊 SSLE Project 2 - Cluster Health Check
========================================

✅ Docker is running

📦 Container Status:
NAMES              STATUS              PORTS
order-node-1       Up 30 seconds       0.0.0.0:8002->8002/tcp
order-node-2       Up 30 seconds       0.0.0.0:8012->8012/tcp
order-node-3       Up 30 seconds       0.0.0.0:8022->8022/tcp
product-service    Up 30 seconds       0.0.0.0:8001-8011->8001-8011/tcp
...
```

---

### Step 2: Verify Cluster Health

```bash
check-cluster
```

**Expected output:**
```
📊 SSLE Project 2 - Cluster Health Check
========================================

✅ Docker is running

📦 Container Status:
...

🔒 BFT Cluster Status:
  ✅ order-node-1 (port 8002): HEALTHY
  ✅ order-node-2 (port 8012): HEALTHY
  ✅ order-node-3 (port 8022): HEALTHY

🗳️  Consensus Status:
{
  "cluster_size": 3,
  "healthy_nodes": 3,
  "quorum_size": 2,
  "quorum_available": true
}

🎯 MTD Service Registry:
{
  "name": "product-service",
  "port": 8001,
  "healthy": true,
  "rotation_count": 0
}
...

📈 Monitoring:
  ✅ Prometheus: http://localhost:9090
  ✅ Grafana: http://localhost:3000 (admin/admin)
  ✅ Wazuh: https://localhost:443

🎉 Health check complete!
```

---

### Step 3: Test Byzantine Fault Tolerance

```bash
test-bft
```

**What this test does:**

1. ✅ **Test 1: Check BFT Cluster Quorum**
   - Verifies all 3 nodes are running
   - Confirms quorum is available (2/3 nodes)

2. ✅ **Test 2: Create Order with Consensus**
   - Creates order requiring consensus voting
   - All 3 nodes must validate and vote
   - Order commits only if 2/3 approve

3. ✅ **Test 3: Test Fault Tolerance**
   - **Stops order-node-2** (simulating Byzantine fault)
   - Creates order with 2/3 quorum
   - **System should continue working!**
   - Restarts node-2

**Expected output:**
```
🧪 Testing Byzantine Fault Tolerance...

Test 1: Checking BFT cluster quorum...
✅ Cluster status:
{
  "cluster_size": 3,
  "healthy_nodes": 3,
  "quorum_size": 2,
  "quorum_available": true,
  "nodes": [
    {"node": "order-node-1:8002", "healthy": true},
    {"node": "order-node-2:8012", "healthy": true},
    {"node": "order-node-3:8022", "healthy": true}
  ]
}

Test 2: Creating order (requires consensus)...
✅ Order created successfully:
{
  "order_id": "ORD-1735211234-order-node-1",
  "customer_id": "CUST001",
  "items": [...],
  "status": "pending",
  "created_by": "order-node-1"
}

Test 3: Testing fault tolerance (stopping node 2)...
Stopping order-node-2...
order-node-2
Creating order with 2/3 quorum...
✅ Order created with 2/3 quorum (Byzantine fault tolerance working!)
{
  "order_id": "ORD-1735211245-order-node-1",
  "customer_id": "CUST002",
  "items": [...],
  "status": "pending"
}

Restarting order-node-2...
order-node-2

🎉 BFT testing complete!
```

**✅ Success criteria:**
- Order created with all nodes: **PASS**
- Order created with 2/3 nodes (one down): **PASS** ← This proves BFT works!
- System recovers when node restarts: **PASS**

---

### Step 4: Test Moving Target Defense

```bash
test-mtd
```

**What this test does:**

1. ✅ **Test 1: Check Service Registry**
   - Lists all registered services
   - Shows current ports and rotation counts

2. ✅ **Test 2: Port Scan (Baseline)**
   - Scans ports 8000-8100
   - Records which ports are open

3. ✅ **Test 3: Trigger MTD Rotation**
   - Forces product-service to rotate to new port
   - Service Registry allocates new port

4. ✅ **Test 4: Verify Service Still Works**
   - Makes request to product-service via API Gateway
   - Gateway uses Service Registry to find new port
   - **Request succeeds even after rotation!**

**Expected output:**
```
🎯 Testing Moving Target Defense...

Test 1: Checking service registry...
✅ Registered services:
{
  "name": "product-service",
  "port": 8001,
  "rotation_count": 0
}
{
  "name": "payment-service",
  "port": 8003,
  "rotation_count": 0
}
{
  "name": "api-gateway",
  "port": 8080,
  "rotation_count": 0
}

Test 2: Port scan (baseline)...
Active ports in range 8000-8100:
  - Port 8001: OPEN (product-service)
  - Port 8002: OPEN (order-node-1)
  - Port 8003: OPEN (payment-service)
  - Port 8012: OPEN (order-node-2)
  - Port 8022: OPEN (order-node-3)
  - Port 8080: OPEN (api-gateway)

Test 3: Triggering MTD rotation for product-service...
✅ Rotation triggered:
{
  "new_port": 8007,
  "rotation_time": "2025-12-26T11:15:00Z",
  "next_rotation": "2025-12-26T11:20:00Z"
}

Waiting for service to rotate to port 8007...

Test 4: Verifying service availability after rotation...
✅ Product service still accessible after rotation!
Products available: 10

🎉 MTD testing complete!

💡 Tip: Run this test multiple times over 10 minutes to see port rotations
```

**✅ Success criteria:**
- Service registers with Registry: **PASS**
- Rotation triggered successfully: **PASS**
- New port allocated (8001 → 8007): **PASS**
- Service accessible after rotation: **PASS** ← This proves MTD works!

**Re-run after 5 minutes:**
```bash
# Wait 5 minutes (automatic rotation interval)
sleep 300

# Check services again
curl http://localhost:5000/services | jq '.services[] | {name, port, rotation_count}'

# You should see:
# {
#   "name": "product-service",
#   "port": 8011,  ← DIFFERENT PORT!
#   "rotation_count": 1  ← Rotation count increased
# }
```

---

### Step 5: Run Full Test Suite

```bash
run-tests
```

This runs:
1. Python unit tests (if they exist in `tests/`)
2. BFT integration tests
3. MTD integration tests

---

## 🔬 Advanced Testing Scenarios

### Scenario 1: Simulate Byzantine Node Attack

```bash
# Inject false data from one node (simulated attack)
curl -X POST http://localhost:8012/consensus/vote \
  -H "Content-Type: application/json" \
  -d '{
    "operation_id": "test123",
    "operation_type": "CREATE_ORDER",
    "operation_data": {
      "order_id": "MALICIOUS-ORDER",
      "customer_id": "HACKER",
      "items": [{"product_id": "FAKE", "quantity": 999999}]
    },
    "proposer": "order-node-1"
  }'

# Expected: Node validates and rejects (votes "reject")
# Check Wazuh for alert: "Byzantine behavior detected"
```

### Scenario 2: Network Partition

```bash
# Create network partition (isolate node-3)
docker network disconnect ecommerce-network order-node-3

# System should continue with 2/3 quorum
test-bft

# Heal partition
docker network connect ecommerce-network order-node-3

# Node-3 should catch up automatically
```

### Scenario 3: Reconnaissance Attack

```bash
# Attacker performs port scan
nmap -p 8000-8100 localhost

# Attacker records open ports
# Wait 5 minutes for MTD rotation
sleep 300

# Attacker scans again
nmap -p 8000-8100 localhost

# Result: Different ports open!
# Attacker's reconnaissance data is now stale
```

### Scenario 4: Load Testing with Byzantine Fault

```bash
# Generate load (100 orders)
for i in {1..100}; do
  curl -X POST http://localhost:8080/proxy/order-service/api/orders \
    -H "Content-Type: application/json" \
    -d "{\"customer_id\": \"CUST$i\", \"items\": [{\"product_id\": \"PROD001\", \"quantity\": 1}]}" &
done

# Wait a bit
sleep 5

# Stop one node during load
docker stop order-node-2

# Generate more load
for i in {101..200}; do
  curl -X POST http://localhost:8080/proxy/order-service/api/orders \
    -H "Content-Type: application/json" \
    -d "{\"customer_id\": \"CUST$i\", \"items\": [{\"product_id\": \"PROD001\", \"quantity\": 1}]}" &
done

# Check Prometheus metrics
curl http://localhost:9090/api/v1/query?query=order_created_total

# Expected: Orders continue being created (BFT tolerance working)
```

---

## 📊 Monitoring During Tests

### Prometheus Queries

Open http://localhost:9090 and run:

```promql
# BFT Consensus success rate
rate(bft_consensus_approved_total[5m]) / rate(bft_consensus_proposals_total[5m])

# MTD rotation frequency
rate(mtd_rotations_total[1h])

# Order processing latency
histogram_quantile(0.95, order_processing_duration_seconds_bucket)

# Active services
registry_active_services

# BFT quorum status
bft_quorum_status
```

### Grafana Dashboards

Open http://localhost:3000 (admin/admin)

1. **BFT Consensus Dashboard**
   - Cluster health
   - Vote statistics
   - Quorum availability

2. **MTD Operations Dashboard**
   - Port rotations over time
   - Service locations
   - Rotation duration

3. **System Performance**
   - Request latency with BFT overhead
   - Throughput
   - Error rates

### Wazuh Alerts

Open https://localhost:443

Check for:
- **Rule 100200**: Byzantine behavior detected
- **Rule 100201**: BFT quorum lost
- **Rule 100210**: MTD rotation anomaly

---

## 🎯 Test Coverage Checklist

### Byzantine Fault Tolerance
- [ ] All nodes healthy, consensus works
- [ ] 1 node down, consensus works (2/3 quorum)
- [ ] 2 nodes down, consensus fails (no quorum) ← Expected
- [ ] Byzantine node injects false data, rejected by majority
- [ ] Network partition, majority partition continues
- [ ] Node recovery, state synchronization

### Moving Target Defense
- [ ] Services register with Registry
- [ ] Manual rotation triggered successfully
- [ ] Automatic rotation after 5 minutes
- [ ] Requests work after rotation (via Registry)
- [ ] Port scan shows different ports over time
- [ ] Zero downtime during rotation

### Integration
- [ ] Order creation triggers consensus
- [ ] Product service accessible via rotating gateway
- [ ] Payment service rotates and remains accessible
- [ ] Monitoring captures all metrics
- [ ] Wazuh detects anomalies

---

## 🐛 Troubleshooting

### Problem: Containers won't start

```bash
# Check Docker daemon
sudo systemctl status docker

# Check logs
docker-compose logs

# Restart everything
stop-project
start-project
```

### Problem: BFT tests fail with "unreachable"

```bash
# Services may still be initializing
check-cluster

# Wait longer
sleep 60

# Retry test
test-bft
```

### Problem: MTD rotation not working

```bash
# Check Registry logs
docker logs service-registry

# Verify MTD is enabled
docker exec product-service env | grep MTD

# Check service registration
curl http://localhost:5000/services
```

### Problem: Port conflicts

```bash
# Find what's using the port
sudo lsof -i :8002

# Kill the process or change ports in docker-compose.yml
```

---

## 📈 Performance Benchmarks

### Expected Metrics

| Metric | Without BFT | With BFT | Overhead |
|--------|-------------|----------|----------|
| Order creation latency | ~50ms | ~150ms | 3x |
| Throughput (req/s) | 1000 | 333 | 67% reduction |
| Consensus time | N/A | ~100ms | - |

| Metric | Without MTD | With MTD | Overhead |
|--------|-------------|----------|----------|
| Request latency | ~20ms | ~25ms | 25% |
| Rotation time | N/A | ~2s | - |
| Service discovery | 0ms (static) | ~5ms | - |

### Run Benchmarks

```bash
# Install k6 (included in Nix shell)
# Create benchmark script
cat > benchmark.js << 'EOF'
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  stages: [
    { duration: '30s', target: 50 },  // Ramp up
    { duration: '1m', target: 50 },   // Steady state
    { duration: '30s', target: 0 },   // Ramp down
  ],
};

export default function () {
  let res = http.post('http://localhost:8080/proxy/order-service/api/orders',
    JSON.stringify({
      customer_id: 'BENCH-CUSTOMER',
      items: [{ product_id: 'PROD001', quantity: 1, price: 99.99 }]
    }),
    { headers: { 'Content-Type': 'application/json' } }
  );
  
  check(res, {
    'status is 201': (r) => r.status === 201,
    'has order_id': (r) => r.json('order_id') !== undefined,
  });
}
EOF

# Run benchmark
k6 run benchmark.js
```

---

## 🎥 Demo Recording

For your demo video:

```bash
# 1. Show architecture
check-cluster

# 2. Demonstrate BFT
echo "=== Test 1: Byzantine Fault Tolerance ==="
test-bft

# 3. Demonstrate MTD
echo "=== Test 2: Moving Target Defense ==="
test-mtd

# 4. Show monitoring
echo "=== Monitoring Dashboards ==="
echo "Prometheus: http://localhost:9090"
echo "Grafana: http://localhost:3000"
echo "Wazuh: https://localhost:443"

# 5. Combined attack scenario
echo "=== Combined Attack: Byzantine + Reconnaissance ==="
# Stop one node
docker stop order-node-2
# Create order (BFT continues)
curl -X POST http://localhost:8080/proxy/order-service/api/orders ...
# Show port rotation
curl http://localhost:5000/services
```

---

## 🎉 Summary

**With the Nix flake, you have:**
- ✅ Automated testing scripts
- ✅ Cluster health monitoring
- ✅ BFT validation tests
- ✅ MTD rotation tests
- ✅ All tools pre-installed
- ✅ One-command deployment

**Testing workflow:**
1. `nix develop` - Enter dev environment
2. `start-project` - Deploy everything
3. `check-cluster` - Verify health
4. `test-bft` - Validate Byzantine tolerance
5. `test-mtd` - Validate Moving Target Defense
6. `run-tests` - Full test suite

**Your project demonstrates:**
- 🛡️ **Byzantine Fault Tolerance** - System continues with 1 failed node
- 🎯 **Moving Target Defense** - Services rotate endpoints, defeating reconnaissance
- 📊 **Monitoring** - Prometheus, Grafana, Wazuh track everything
- 🚀 **Scalability** - Distributed, containerized architecture

Good luck with your evaluation! 🎓
