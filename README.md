# SSLE Project 2 - Attack Tolerance Mechanisms

**Course**: Security in Large Scale Systems  
**Institution**: Universidade de Aveiro - DETI  
**Student**: Luis Godinho  
**Project**: Attack Tolerance Mechanisms for E-commerce Platform

## 🎯 Project Overview

This project implements **Attack Tolerance Mechanisms** for a scalable e-commerce platform, focusing on:
1. **Byzantine Fault Tolerance (BFT)** - Consensus-based order processing
2. **Moving Target Defense (MTD)** - Dynamic service endpoint rotation

**Integration Bonus**: This project builds upon [ssle_project1](https://github.com/luis-godinho/ssle_project1) and can be integrated with its threat detection capabilities for a complete security solution.

---

## 📋 Table of Contents

- [Architecture Overview](#architecture-overview)
- [Attack Tolerance Mechanisms](#attack-tolerance-mechanisms)
- [Risk Management](#risk-management)
- [Service Architecture](#service-architecture)
- [Deployment](#deployment)
  - [Quick Start with Nix](#quick-start-with-nix-recommended)
  - [Quick Start with Docker](#quick-start-with-docker)
- [Testing & Validation](#testing--validation)
- [Monitoring & Evaluation](#monitoring--evaluation)
- [Integration with Project 1](#integration-with-project-1)

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Service Registry (MTD)                        │
│          Dynamic Service Discovery - Port 5000                   │
│              Tracks: Location, Health, Rotation                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
    │ Product │    │ Payment │    │  Email  │
    │ Service │    │ Service │    │ Service │
    │  :8001  │    │  :8003  │    │  :25    │
    │  (MTD)  │    │  (MTD)  │    │  (MTD)  │
    └────┬────┘    └────┬────┘    └────┬────┘
         │               │               │
         └───────────────┼───────────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
    ┌────▼─────────────────────────┐    │
    │   Order Service Cluster      │    │
    │   (Byzantine Fault Tolerance)│    │
    │                              │    │
    │  ┌──────┐  ┌──────┐  ┌──────┐│   │
    │  │Node 1│  │Node 2│  │Node 3││   │
    │  │:8002 │  │:8012 │  │:8022 ││   │
    │  └──┬───┘  └──┬───┘  └──┬───┘│   │
    │     └─────────┼─────────┘    │   │
    │            Consensus          │   │
    │         (2f+1 agreement)      │   │
    └──────────────┬────────────────┘   │
                   │                    │
         ┌─────────┴────────────────────┘
         │
    ┌────▼─────┐
    │   API    │
    │ Gateway  │
    │  :8080   │
    │ (MTD +   │
    │  Load    │
    │ Balance) │
    └────┬─────┘
         │
    ┌────▼─────┐
    │   Web    │
    │ Service  │
    │  :80     │
    └──────────┘
         │
    ┌────▼─────────────┐
    │   Monitoring      │
    │ • Prometheus :9090│
    │ • Grafana   :3000 │
    │ • Wazuh     :443  │
    │ • Vault     :8200 │
    └───────────────────┘
```

---

## 🛡️ Attack Tolerance Mechanisms

### 1. Byzantine Fault Tolerance (BFT)

**Purpose**: Tolerate Byzantine faults in the Order Service where nodes may fail arbitrarily or behave maliciously.

**Implementation**:
- **3 Order Service replicas** (tolerates 1 Byzantine fault: f=1, needs 2f+1=3 nodes)
- **Consensus protocol** for critical operations:
  - Order creation
  - Order status updates
  - Payment confirmations
- **State replication** across all nodes
- **Vote-based decision making** (requires 2/3 agreement)

**Fault Scenarios Tolerated**:
1. **Crash failures**: One node goes down
2. **Network partitions**: Temporary isolation of nodes
3. **Malicious nodes**: Compromised node sending incorrect data
4. **Timing failures**: Slow or unresponsive nodes

**Consensus Flow**:
```
1. Client → Gateway → Order Node 1 (Leader)
2. Leader proposes operation to all replicas
3. Each replica validates and votes
4. If 2/3 nodes agree → commit operation
5. All nodes update state
6. Response sent to client
```

**Validation**:
- **Test 1**: Stop one node → System continues (2/3 quorum)
- **Test 2**: Inject false data from one node → Rejected by majority
- **Test 3**: Network partition → Majority partition continues

### 2. Moving Target Defense (MTD)

**Purpose**: Prevent attackers from mapping the system architecture by continuously changing service endpoints.

**Implementation**:
- **Dynamic port allocation** for all services
- **Periodic endpoint rotation** (every 5 minutes)
- **Service Registry tracks** current locations
- **Zero-downtime migration** between endpoints
- **Geographic/logical location diversity**

**Rotation Strategy**:
```python
# Services rotate through port ranges:
- Product Service:  8001-8011 (11 ports)
- Payment Service:  8003-8013 (11 ports)
- Email Service:    25, 2525-2534 (11 ports)
- API Gateway:      8080-8090 (11 ports)
```

**Rotation Process**:
1. Service starts on initial port
2. After TTL expires (5 min), service requests new port from Registry
3. Service starts new instance on new port
4. Registry updates service location
5. Health check validates new endpoint
6. Old endpoint drains connections (30s grace period)
7. Old instance shuts down

**Attack Surface Reduction**:
- **Before MTD**: Attacker scans once, knows all endpoints forever
- **With MTD**: Attacker must continuously scan, endpoints change faster than reconnaissance

**Validation**:
- **Test 1**: Service rotates ports every 5 minutes
- **Test 2**: Client requests always routed correctly (via Registry)
- **Test 3**: Port scan shows different endpoints over time

---

## ⚠️ Risk Management

### Fault 1: Byzantine Faults in Order Processing

**Threat**: Compromised or malfunctioning Order Service nodes could:
- Process fraudulent orders
- Modify order totals
- Steal payment information
- Deny service to legitimate customers
- Create financial discrepancies

**Attack Surface**:
- Order Service API endpoints
- Inter-service communication channels
- Database connections
- Payment gateway integration

**Likelihood**: Medium (requires compromising service infrastructure)
**Impact**: Critical (financial loss, data breach, reputation damage)

**Mitigation Strategy** (BFT):
1. **3-node consensus cluster** (2f+1 where f=1)
2. **State machine replication** across nodes
3. **Vote verification** for every operation
4. **Cryptographic signatures** on all messages
5. **Audit logging** of all votes and decisions
6. **Quorum-based commits** (requires 67% agreement)

**Risk Reduction**: High → Low
- Single node compromise cannot affect outcomes
- System continues operating with 1 failed node
- Malicious behavior detected via vote discrepancies

### Fault 2: Reconnaissance and Targeted Attacks

**Threat**: Attackers performing reconnaissance to:
- Map service architecture
- Identify vulnerable endpoints
- Plan coordinated attacks
- Exploit known service vulnerabilities
- Launch DDoS on specific services

**Attack Surface**:
- Fixed service endpoints and ports
- Predictable service locations
- Static network topology
- Long-lived connections
- Service fingerprinting

**Likelihood**: High (reconnaissance is often the first attack phase)
**Impact**: High (enables targeted, effective attacks)

**Mitigation Strategy** (MTD):
1. **Port rotation** every 5 minutes
2. **Dynamic service discovery** via Registry
3. **Randomized rotation schedule**
4. **Endpoint diversity** (10+ ports per service)
5. **Geographic distribution** (future: multi-region)
6. **Connection draining** during rotation

**Risk Reduction**: High → Low
- Reconnaissance data expires quickly (5 min)
- Attack planning disrupted by moving targets
- Automated attacks fail due to endpoint changes
- Increased attacker cost and complexity

---

## 🚀 Deployment

### Prerequisites

**Option A: With Nix Flakes (Recommended)**
```bash
# Nix with flakes enabled
nix --version  # Should be 2.4+

# Enable flakes in ~/.config/nix/nix.conf:
experimental-features = nix-command flakes
```

**Option B: With Docker**
```bash
# System Requirements
- Docker 20.10+
- Docker Compose 2.0+
- 16GB+ RAM
- 50GB+ disk space

# Ports Required
- 80, 443      (Web, Wazuh)
- 5000         (Registry)
- 8001-8011    (Product Service MTD range)
- 8002,8012,8022 (Order Service BFT cluster)
- 8003-8013    (Payment Service MTD range)
- 8080-8090    (API Gateway MTD range)
- 25,2525-2534 (Email Service MTD range)
- 3000         (Grafana)
- 8200         (Vault)
- 9090         (Prometheus)
```

---

### Quick Start with Nix (Recommended)

```bash
# Clone repository
git clone https://github.com/luis-godinho/ssle_project2.git
cd ssle_project2

# Enter development environment (installs all tools)
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

# Start everything
start-project

# Check health
check-cluster

# Test BFT
test-bft

# Test MTD
test-mtd
```

**What the Nix shell provides:**
- ✅ Docker & Docker Compose
- ✅ Python 3.11 with all dependencies
- ✅ curl, jq, netcat, nmap
- ✅ Custom testing scripts
- ✅ Automated cluster management
- ✅ No manual installation needed!

**See [TESTING_GUIDE.md](TESTING_GUIDE.md) for comprehensive testing instructions.**

---

### Quick Start with Docker

```bash
# Clone repository
git clone https://github.com/luis-godinho/ssle_project2.git
cd ssle_project2

# Initialize Vault secrets
./scripts/init-vault.sh

# Start all services
docker-compose up -d

# Check cluster status
./scripts/check-cluster.sh

# View service locations
curl http://localhost:5000/services
```

### Verify Deployment

```bash
# Check BFT cluster quorum
curl http://localhost:8002/consensus/status

# Expected output:
{
  "cluster_size": 3,
  "healthy_nodes": 3,
  "quorum_available": true,
  "current_leader": "order-node-1",
  "nodes": [
    {"id": "order-node-1", "port": 8002, "status": "healthy"},
    {"id": "order-node-2", "port": 8012, "status": "healthy"},
    {"id": "order-node-3", "port": 8022, "status": "healthy"}
  ]
}

# Check MTD rotation status
curl http://localhost:5000/services

# Expected output:
{
  "services": [
    {
      "name": "product-service",
      "current_port": 8005,
      "next_rotation": "2025-12-23T12:35:00Z",
      "rotations_count": 12
    },
    ...
  ]
}
```

---

## 🧪 Testing & Validation

> **📖 Full testing guide available**: See [TESTING_GUIDE.md](TESTING_GUIDE.md) for comprehensive testing instructions with Nix.

### Quick Test Commands (with Nix)

```bash
# Inside nix develop shell:

test-bft      # Test Byzantine Fault Tolerance
test-mtd      # Test Moving Target Defense
run-tests     # Run full test suite
check-cluster # Check cluster health
```

### Manual Testing

### Test 1: Byzantine Fault Tolerance

#### Scenario 1.1: Node Crash Tolerance
```bash
# Stop one Order Service node
docker stop order-node-2

# Create order (should succeed with 2/3 quorum)
curl -X POST http://localhost:8080/proxy/order-service/api/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST001",
    "items": [{"product_id": "PROD001", "quantity": 1}]
  }'

# Expected: Order created successfully
# Result: 2/3 nodes voted, operation committed ✅
```

#### Scenario 1.2: Byzantine Node Behavior
```bash
# Inject false data via one node
./scripts/inject-byzantine-fault.sh order-node-3

# Expected: Order rejected due to vote disagreement
# Wazuh Alert: "Byzantine behavior detected" ✅
```

### Test 2: Moving Target Defense

#### Scenario 2.1: Port Rotation
```bash
# Monitor service location before rotation
curl http://localhost:5000/discover/product-service
# Result: {"url": "http://product-service:8001"}

# Wait 5 minutes or trigger rotation
./scripts/trigger-rotation.sh product-service

# Monitor service location after rotation
curl http://localhost:5000/discover/product-service
# Result: {"url": "http://product-service:8007"} ✅

# Verify requests still work
curl http://localhost:8080/proxy/product-service/api/products
# Result: Products returned successfully ✅
```

#### Scenario 2.2: Attack Surface Validation
```bash
# Scan ports before MTD
nmap -p 8000-8100 localhost
# Result: 5 open ports

# Wait 10 minutes for rotations

# Scan ports after MTD
nmap -p 8000-8100 localhost
# Result: Different 5 open ports ✅
# Attacker's reconnaissance is now stale!
```

---

## 📊 Monitoring & Evaluation

### Access Monitoring Dashboards

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **Wazuh**: https://localhost:443
- **Service Registry**: http://localhost:5000/services

### Prometheus Queries

```promql
# BFT Consensus Success Rate
rate(bft_consensus_approved_total[5m]) / rate(bft_consensus_proposals_total[5m])

# BFT Quorum Availability
bft_quorum_status

# MTD Rotation Frequency
rate(mtd_rotations_total[1h])

# Order Processing Latency (with BFT overhead)
histogram_quantile(0.95, order_processing_duration_seconds_bucket)
```

### Grafana Dashboards

1. **BFT Consensus Dashboard**
   - Cluster health status
   - Vote statistics
   - Quorum availability
   - Byzantine behavior alerts

2. **MTD Operations Dashboard**
   - Port rotations over time
   - Service location map
   - Rotation duration

3. **System Performance Dashboard**
   - Request latency (BFT/MTD overhead)
   - Throughput
   - Error rates

### Wazuh Custom Rules

- **Rule 100200**: Byzantine behavior detected
- **Rule 100201**: BFT quorum lost (Critical)
- **Rule 100210**: MTD rotation anomaly
- **Rule 100211**: Service impersonation attempt

---

## 🔗 Integration with Project 1

**This project can be integrated with [ssle_project1](https://github.com/luis-godinho/ssle_project1) for a complete security solution:**

### Combined Architecture Benefits:

1. **Project 1 (Threat Detection)** provides:
   - Shellshock detection (Web Service)
   - DoS/DDoS protection (API Gateway)
   - Spam filtering (Email Service)
   - Wazuh SIEM integration

2. **Project 2 (Attack Tolerance)** provides:
   - Byzantine fault tolerance (Order Service)
   - Moving Target Defense (All Services)
   - Service resilience
   - Attack surface reduction

3. **Integration Points**:
   - **Shared Wazuh instance**: Unified security monitoring
   - **Shared Prometheus**: Combined metrics and alerting
   - **API Gateway**: Routes to both threat detection and tolerant services
   - **Service Registry**: Manages both static and rotating endpoints

### Integration Steps:

```bash
# 1. Clone both projects
git clone https://github.com/luis-godinho/ssle_project1.git
git clone https://github.com/luis-godinho/ssle_project2.git

# 2. Use integrated docker-compose
cd ssle_project2
docker-compose -f docker-compose.integrated.yml up -d

# 3. Result: Full security stack
# - Threat Detection (Project 1)
# - Attack Tolerance (Project 2)
# - Unified Monitoring
```

**Integration Bonus**: +3 units for demonstrating combined threat detection and attack tolerance.

---

## 📚 Documentation Files

- **[README.md](README.md)** - This file (project overview)
- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Comprehensive testing guide with Nix
- **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** - Code implementation details
- **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** - Quick reference and checklist
- **[flake.nix](flake.nix)** - Nix development environment

---

## 🛠️ Project Structure

```
ssle_project2/
├── flake.nix                   # Nix development environment ⭐ NEW
├── TESTING_GUIDE.md            # Comprehensive testing guide ⭐ NEW
├── IMPLEMENTATION_GUIDE.md     # Code implementation details
├── PROJECT_SUMMARY.md          # Quick reference
├── docker-compose.yml          # Main deployment
├── services/
│   ├── registry/               # Service Registry (MTD)
│   ├── order-service/          # BFT cluster (3 nodes)
│   ├── product-service/        # Product API (MTD)
│   ├── payment-service/        # Payment API (MTD)
│   ├── email-service/          # Email service (MTD)
│   ├── api-gateway/            # Load balancer (MTD)
│   └── web-service/            # Frontend
├── monitoring/
│   ├── prometheus/
│   ├── grafana/
│   └── alertmanager/
├── wazuh/
│   └── custom_rules.xml
├── vault/
└── scripts/
```

---

## 📚 References

1. **Byzantine Fault Tolerance**:
   - Castro, M., & Liskov, B. (1999). Practical Byzantine fault tolerance.
   - Schneider, F. B. (1990). Implementing fault-tolerant services using the state machine approach.

2. **Moving Target Defense**:
   - Okhravi, H., et al. (2013). Finding focus in the blur of moving-target techniques.
   - Jajodia, S., et al. (2011). Moving target defense: Creating asymmetric uncertainty for cyber threats.

3. **Distributed Systems**:
   - Tanenbaum, A. S., & Van Steen, M. (2017). Distributed systems: principles and paradigms.

---

## 📄 License

Academic project for SSLE course - Universidade de Aveiro

---

## 👤 Author

**Luis Godinho**  
Universidade de Aveiro - DETI  
SSLE 2025

**Projects**:
- [ssle_project1](https://github.com/luis-godinho/ssle_project1) - Threat Detection
- [ssle_project2](https://github.com/luis-godinho/ssle_project2) - Attack Tolerance (this project)
