# 🧪 Security Testing Suite

Comprehensive test scripts for demonstrating all security features of the Secure E-Commerce Platform.

## 📋 Available Tests

### 🎯 **test-all.sh** - Complete Security Demo

**The ultimate demonstration script** that showcases all three security mechanisms in one flow.

```bash
chmod +x scripts/test-all.sh
./scripts/test-all.sh
```

**What it tests:**
- ✅ HashiCorp Vault secret management
- ✅ Moving Target Defense (MTD) port hopping
- ✅ Byzantine Fault Tolerance (BFT) consensus
- ✅ System resilience under failures

**Duration:** ~2 minutes  
**Best for:** Project demos, presentations, comprehensive verification

---

### 🎯 **test-mtd.sh** - Moving Target Defense

Detailed testing of MTD port hopping mechanism using iptables NAT.

```bash
chmod +x scripts/test-mtd.sh
./scripts/test-mtd.sh
```

**What it tests:**
1. ✅ iptables NAT rule verification (core MTD mechanism)
2. ✅ Port rotation trigger
3. ✅ Old port closure
4. ✅ New port activation
5. ✅ Zero-downtime verification
6. ✅ API Gateway auto-discovery
7. ✅ Multiple rotation stress test
8. ✅ Metrics collection

**Key verifications:**
- External port changes (e.g., 8001 → 8005)
- Internal port stays fixed (8000)
- iptables rules update correctly
- Service continues operating during rotation

**Duration:** ~30 seconds  
**Best for:** MTD-specific demonstrations, security research

---

### 🧬 **test-bft.sh** - Byzantine Fault Tolerance

Comprehensive testing of BFT consensus mechanism.

```bash
chmod +x scripts/test-bft.sh
./scripts/test-bft.sh
```

**What it tests:**
1. ✅ 3-node cluster health check
2. ✅ Load balancing distribution (round-robin)
3. ✅ 3/3 full consensus (all nodes agree)
4. ✅ 2/3 Byzantine fault tolerance (1 node fails)
5. ✅ 1/3 quorum rejection (safety mechanism)
6. ✅ Cluster recovery after failures

**Key verifications:**
- Consensus achieved with majority (2/3)
- System rejects requests without quorum
- Load balances across healthy nodes
- Automatic failover works

**Duration:** ~40 seconds  
**Best for:** BFT-specific demonstrations, consensus algorithm validation

---

## 🚀 Quick Start

### Prerequisites

```bash
# Start all services
docker-compose up -d

# Wait for services to be ready (~30 seconds)
sleep 30

# Verify services are running
docker-compose ps
```

### Run All Tests

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Run complete demo (recommended for first time)
./scripts/test-all.sh

# Or run individual tests
./scripts/test-mtd.sh
./scripts/test-bft.sh
```

---

## 📊 Test Output Examples

### MTD Test Output

```
🎯 Testing Moving Target Defense (MTD)...
============================================

Test 1: Checking service registry...
✅ Registered services:
{
  "name": "product-service",
  "port": 8001,
  "rotation_count": 5
}

Test 2: Verifying iptables NAT rules...
✅ iptables rules found:
  🔀 External port 8001 → Internal port 8000

Test 5: Triggering MTD rotation...
✅ Rotation triggered: 8001 → 8008

Test 7: Verifying old port (8001) is closed...
✅ Old port 8001 is CLOSED (MTD working!)

Test 8: Verifying new port (8008) is open...
✅ New port 8008 is OPEN and responding!

🎉 MTD port rotation verified!
```

### BFT Test Output

```
🧪 Testing Byzantine Fault Tolerance (BFT)...
============================================

Test 1: Checking BFT cluster nodes...
  ✅ order-node-1 is running
  ✅ order-node-2 is running
  ✅ order-node-3 is running

Test 4: Creating order with full cluster (3/3 consensus)...
✅ Order ORD-1234 created with 3/3 consensus

Test 5: Testing Byzantine fault tolerance (stopping node-2)...
✅ Order ORD-1235 created with 2/3 quorum
🛡️  Byzantine fault tolerance WORKING!

Test 6: Testing quorum failure (only 1/3)...
✅ Order correctly REJECTED (quorum not met)!
🛡️  BFT safety mechanism WORKING!

🎉 BFT Testing Complete!
```

---

## 🔧 Troubleshooting

### Services Not Running

```bash
# Check docker-compose status
docker-compose ps

# Restart services
docker-compose down
docker-compose up -d

# Check logs
docker-compose logs -f
```

### MTD Not Working

```bash
# Check iptables rules
docker exec product-service iptables -t nat -L -n -v

# Verify NET_ADMIN capability
docker inspect product-service | grep -i cap_add

# Check product-service logs
docker logs product-service | grep -i mtd
```

### BFT Consensus Failing

```bash
# Check all nodes are running
docker-compose ps | grep order-node

# Verify cluster connectivity
for port in 8102 8112 8122; do
  curl -s http://localhost:$port/health | jq .node_id
done

# Check consensus logs
docker logs order-node-1 | grep -i consensus
```

---

## 📈 Metrics & Monitoring

### Prometheus Metrics

```bash
# MTD metrics
curl -s http://localhost:8001/metrics | grep mtd
# mtd_rotations_total
# mtd_current_port

# BFT metrics
curl -s http://localhost:8102/metrics | grep consensus
# consensus_proposals_total
# consensus_agreements_total
```

### Grafana Dashboards

Access Grafana at: http://localhost:3000  
Credentials: `admin` / `admin`

Pre-configured dashboards:
- **MTD Dashboard**: Port rotation timeline
- **BFT Dashboard**: Consensus metrics and node health

### Wazuh Security Monitoring

Access Wazuh at: https://localhost:443  
Credentials: `admin` / `SecretPassword`

Monitored events:
- Port rotation events (MTD)
- Consensus failures (BFT)
- Security alerts

---

## 🎓 Understanding the Tests

### How MTD Works

```
┌─────────────────┐
│ Client Request  │
│ to port 8001    │
└────────┬────────┘
         │
         ↓
┌────────────────────┐
│ iptables NAT       │  ← Port hopping happens here
│ 8001 → 8000       │  ← Rule changes on rotation
└────────┬───────────┘
         │
         ↓
┌────────────────────┐
│ Flask Service      │  ← Always on port 8000
│ (Internal: 8000)   │  ← Never restarts!
└────────────────────┘
```

**Benefits:**
- Zero downtime during rotation
- Attack surface constantly changing
- Automated or manual rotation
- Transparent to clients (via registry)

### How BFT Works

```
Client Request
     ↓
API Gateway (Load Balancer)
     ↓
┌─────────────────────────────┐
│   BFT Consensus Cluster     │
├─────────┬─────────┬─────────┤
│ Node 1  │ Node 2  │ Node 3  │
│  (f=1)  │         │         │
└─────────┴─────────┴─────────┘
     ↓         ↓         ↓
  Vote 1    Vote 2    Vote 3
     └─────────┬─────────┘
               ↓
        Quorum: 2/3
               ↓
      Consensus Achieved!
```

**Properties:**
- **f = 1**: Tolerates 1 Byzantine (malicious) node
- **n = 3**: Total nodes
- **Quorum = ⌈(n+f+1)/2⌉ = 2**: Required for consensus
- **Safety**: Rejects without quorum
- **Liveness**: Works with majority

---

## 🎯 Demo Script for Presentations

For live demonstrations, follow this narrative:

### 1. Introduction (30 sec)

```bash
# "This is a secure e-commerce platform with three advanced security mechanisms"
./scripts/test-all.sh
```

### 2. Moving Target Defense Demo (1 min)

```bash
# "First, let's see how MTD prevents attackers from targeting fixed ports"
curl http://localhost:5000/services | jq '.services[] | select(.name=="product-service")'

# "Service is on port 8001. Let's trigger a rotation."
curl -X POST http://localhost:5000/rotate/product-service -H "Content-Type: application/json"

# "Now the service moved to port 8008. Old port is closed."
curl http://localhost:8001/api/products  # Fails
curl http://localhost:8008/api/products  # Works!
```

### 3. Byzantine Fault Tolerance Demo (1 min)

```bash
# "Now let's demonstrate fault tolerance. We have 3 order-processing nodes."
curl http://localhost:8102/consensus/status | jq

# "Let's simulate a node failure"
docker stop order-node-2

# "System still works with 2/3 nodes"
curl -X POST http://localhost:8080/proxy/order-service/api/orders \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "DEMO", "items": [{"product_id": "PROD001", "quantity": 1, "price": 999.99}]}'

# "Restore the node"
docker start order-node-2
```

### 4. Conclusion (30 sec)

"This platform demonstrates three critical security features:
- **Vault** for secret management
- **MTD** for attack surface reduction
- **BFT** for Byzantine fault tolerance

All working together to create a highly secure and resilient system."

---

## 📚 Additional Resources

- **Project Documentation**: `../README.md`
- **Architecture Diagrams**: `../docs/architecture.md`
- **Security Analysis**: `../docs/security.md`
- **API Documentation**: `../docs/api.md`

---

## 🤝 Contributing

To add new tests:

1. Create test script in `scripts/`
2. Make it executable: `chmod +x scripts/your-test.sh`
3. Follow naming convention: `test-<feature>.sh`
4. Add color-coded output for clarity
5. Include verification steps
6. Document in this README

---

## 📝 License

Part of the Secure E-Commerce Platform project.
