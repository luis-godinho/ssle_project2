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

## 🏢 Service Architecture

### Core Services

#### 1. Service Registry (Port 5000)
**Purpose**: Central service discovery with MTD support

**Key Features**:
- Service registration with dynamic ports
- Health monitoring and heartbeats
- Port allocation and rotation management
- Service location tracking
- Geographic/logical location metadata

**Endpoints**:
- `POST /register` - Register service with current port
- `POST /rotate/{service}` - Request new port allocation
- `GET /discover/{service}` - Get current service location
- `GET /services` - List all services and locations
- `GET /health` - Registry health check

#### 2. Order Service Cluster (Ports 8002, 8012, 8022)
**Purpose**: Byzantine fault-tolerant order processing

**Key Features**:
- 3-node consensus cluster (BFT)
- Leader election and rotation
- State machine replication
- Vote-based decision making
- Order validation and processing
- Payment coordination
- Stock management

**Consensus Operations**:
- `CREATE_ORDER` - Requires 2/3 votes
- `UPDATE_STATUS` - Requires 2/3 votes
- `CANCEL_ORDER` - Requires 2/3 votes
- `PROCESS_PAYMENT` - Requires unanimous votes (3/3)

**Endpoints** (per node):
- `POST /api/orders` - Create order (triggers consensus)
- `GET /api/orders/{id}` - Get order details
- `PUT /api/orders/{id}/status` - Update status (triggers consensus)
- `POST /api/orders/{id}/cancel` - Cancel order (triggers consensus)
- `GET /consensus/status` - Cluster health and quorum status
- `GET /consensus/votes/{operation_id}` - View votes for operation

#### 3. Product Service (Ports 8001-8011 rotating)
**Purpose**: Product catalog with MTD

**Key Features**:
- Product CRUD operations
- Stock management
- MTD port rotation
- Integration with Order Service consensus

#### 4. Payment Service (Ports 8003-8013 rotating)
**Purpose**: Payment processing with MTD

**Key Features**:
- Payment validation
- Transaction processing
- MTD port rotation
- Secure credential handling

#### 5. Email Service (Ports 25, 2525-2534 rotating)
**Purpose**: Email notifications with MTD

**Key Features**:
- Order confirmations
- Status update notifications
- MTD port rotation

#### 6. API Gateway (Ports 8080-8090 rotating)
**Purpose**: Load balancing and routing with MTD

**Key Features**:
- Routes to Order Service cluster (round-robin)
- Dynamic service discovery
- MTD port rotation
- Rate limiting
- Health checks

### Infrastructure Services

#### 7. Prometheus (Port 9090)
**Metrics Collected**:
- `bft_consensus_proposals_total` - Consensus proposals
- `bft_consensus_votes_total` - Votes cast (approved/rejected)
- `bft_quorum_status` - Current quorum availability
- `bft_node_health` - Node health status
- `mtd_rotations_total` - Service rotations completed
- `mtd_active_ports` - Current port allocations
- `mtd_rotation_duration_seconds` - Rotation time

#### 8. Grafana (Port 3000)
**Dashboards**:
- BFT Consensus Monitoring
- MTD Rotation Status
- Service Health Overview
- Order Processing Metrics

#### 9. Wazuh (Port 443)
**Custom Rules**:
- Byzantine behavior detection
- Vote discrepancy alerts
- Quorum loss warnings
- Rotation anomalies
- Service impersonation attempts

#### 10. HashiCorp Vault (Port 8200)
**Purpose**: Distributed secret management

**Key Features**:
- Service authentication tokens
- Database credentials
- API keys rotation
- Encryption keys
- Certificate management

---

## 🚀 Deployment

### Prerequisites

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

### Quick Start

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
# Verify: Check consensus votes
curl http://localhost:8002/consensus/votes/{operation_id}

# Result: 2/3 nodes voted, operation committed
```

#### Scenario 1.2: Byzantine Node Behavior
```bash
# Inject false data via one node
./scripts/inject-byzantine-fault.sh order-node-3

# Attempt order creation
curl -X POST http://localhost:8080/proxy/order-service/api/orders \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "CUST002", "items": [...]}'

# Expected: Order rejected due to vote disagreement
# Verify: Check Wazuh alerts
# Alert: "Byzantine behavior detected: Node order-node-3 vote mismatch"
```

#### Scenario 1.3: Network Partition
```bash
# Create network partition
./scripts/create-partition.sh order-node-3

# Verify majority partition continues
curl http://localhost:8002/consensus/status
# Result: 2/3 nodes healthy, quorum available

# Heal partition
./scripts/heal-partition.sh order-node-3

# Verify node catches up
curl http://localhost:8022/consensus/status
# Result: Node synchronized with cluster
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
# Result: {"url": "http://product-service:8007"}

# Verify requests still work
curl http://localhost:8080/proxy/product-service/api/products
# Result: Products returned successfully
```

#### Scenario 2.2: Attack Surface Validation
```bash
# Scan ports before MTD
nmap -p 8000-8100 localhost
# Result: 5 open ports (fixed endpoints)

# Enable MTD and wait 10 minutes

# Scan ports after MTD
nmap -p 8000-8100 localhost
# Result: Different 5 open ports (rotated endpoints)

# Compare scans
./scripts/compare-port-scans.sh
# Result: 0% overlap in active ports
```

#### Scenario 2.3: Zero-Downtime Rotation
```bash
# Generate continuous load
ab -n 10000 -c 10 http://localhost:8080/proxy/product-service/api/products &

# Trigger rotation during load
./scripts/trigger-rotation.sh product-service

# Check request success rate
# Expected: >99.9% success rate (no dropped requests)
```

### Test 3: Combined Tolerance

#### Scenario 3.1: BFT + MTD Under Attack
```bash
# Start attack simulation
./scripts/simulate-attack.sh

# Attack includes:
# - DDoS on known ports
# - Byzantine node compromise attempt
# - Network disruption

# Monitor system response:
# 1. MTD rotates endpoints (attack follows old ports)
# 2. BFT cluster maintains quorum (Byzantine node isolated)
# 3. Orders continue processing

# Verify metrics
curl http://localhost:9090/api/v1/query?query=bft_consensus_success_rate
# Expected: >95% success rate
```

---

## 📊 Monitoring & Evaluation

### Prometheus Queries

```promql
# BFT Consensus Success Rate
rate(bft_consensus_approved_total[5m]) / rate(bft_consensus_proposals_total[5m])

# BFT Quorum Availability
bft_quorum_status

# MTD Rotation Frequency
rate(mtd_rotations_total[1h])

# MTD Rotation Duration
histogram_quantile(0.95, mtd_rotation_duration_seconds_bucket)

# Order Processing Latency (with BFT overhead)
histogram_quantile(0.95, order_processing_duration_seconds_bucket)

# Service Availability (with MTD)
avg_over_time(up{job="services"}[5m])
```

### Grafana Dashboards

1. **BFT Consensus Dashboard**
   - Cluster health status
   - Vote statistics
   - Quorum availability timeline
   - Node synchronization lag
   - Byzantine behavior alerts

2. **MTD Operations Dashboard**
   - Active port allocations
   - Rotation timeline
   - Service location map
   - Rotation duration histogram
   - Failed rotation count

3. **System Performance Dashboard**
   - Request latency (with BFT/MTD overhead)
   - Throughput
   - Error rates
   - Resource utilization

### Wazuh Rules

```xml
<!-- Byzantine Behavior Detection -->
<rule id="100200" level="12">
  <if_sid>100000</if_sid>
  <match>vote_mismatch</match>
  <description>Byzantine fault detected: Vote mismatch in consensus</description>
  <group>bft,attack_tolerance</group>
</rule>

<!-- Quorum Loss Alert -->
<rule id="100201" level="14">
  <if_sid>100000</if_sid>
  <match>quorum_lost</match>
  <description>Critical: BFT quorum lost - only $(nodes) nodes available</description>
  <group>bft,attack_tolerance,critical</group>
</rule>

<!-- MTD Rotation Anomaly -->
<rule id="100210" level="8">
  <if_sid>100000</if_sid>
  <match>rotation_failed</match>
  <description>MTD rotation failed for $(service)</description>
  <group>mtd,attack_tolerance</group>
</rule>

<!-- Service Impersonation Attempt -->
<rule id="100211" level="12">
  <if_sid>100000</if_sid>
  <match>invalid_service_port</match>
  <description>Potential service impersonation: Request to non-registered port</description>
  <group>mtd,attack_tolerance</group>
</rule>
```

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

## 📝 Report Structure

The full report follows the required structure:

1. **Introduction**
   - Project objectives
   - Attack tolerance importance
   - Chosen mechanisms rationale

2. **Service Architecture**
   - E-commerce platform description
   - Microservices design
   - Service discovery pattern
   - Scalability considerations

3. **Risk Management and Mitigation**
   - Byzantine faults analysis
   - Reconnaissance attacks analysis
   - Attack surfaces
   - Mitigation strategies

4. **Byzantine Fault Tolerance Approach**
   - Consensus protocol design
   - State machine replication
   - Quorum requirements
   - Implementation details

5. **Moving Target Defense Approach**
   - Port rotation strategy
   - Dynamic service discovery
   - Zero-downtime migration
   - Implementation details

6. **Evaluation**
   - Performance metrics
   - Scalability testing
   - Fault injection results
   - Attack simulation results
   - Overhead analysis

7. **Conclusions**
   - Effectiveness summary
   - Limitations and trade-offs
   - Future improvements
   - Integration possibilities

---

## 🎥 Demo Video

**Demo Strategy** (as per project requirements):

1. **Explain Byzantine Faults**
   - What: Arbitrary node failures/malicious behavior
   - Why relevant: Financial system integrity
   - How exploited: Compromised nodes, network attacks

2. **Demonstrate BFT**
   - Show consensus voting
   - Stop one node → system continues
   - Inject false data → rejected by majority
   - Show Wazuh alerts for Byzantine behavior

3. **Explain Reconnaissance Attacks**
   - What: Mapping system architecture
   - Why relevant: Enables targeted attacks
   - How exploited: Port scanning, service enumeration

4. **Demonstrate MTD**
   - Show port rotation over time
   - Port scan before/after rotation
   - Requests continue working (via Registry)
   - Show attacker confusion (old ports dead)

5. **Combined Attack Scenario**
   - Simultaneous Byzantine + reconnaissance
   - System maintains operation
   - Show metrics and alerts

---

## 🛠️ Project Structure

```
ssle_project2/
├── services/
│   ├── registry/                # Service Registry (MTD coordinator)
│   │   ├── app.py              # Registry with port allocation
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── order-service/          # BFT Order Service Cluster
│   │   ├── app.py              # Consensus implementation
│   │   ├── consensus.py        # BFT consensus protocol
│   │   ├── state_machine.py    # Replicated state machine
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── product-service/        # Product Service (MTD)
│   │   ├── app.py              # Product API with rotation
│   │   ├── mtd_client.py       # MTD rotation client
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── payment-service/        # Payment Service (MTD)
│   ├── email-service/          # Email Service (MTD)
│   ├── api-gateway/            # API Gateway (MTD + Load Balancer)
│   └── web-service/            # Web Frontend
│
├── monitoring/
│   ├── prometheus/
│   │   ├── prometheus.yml      # Scrape configs
│   │   ├── alerts.yml          # BFT/MTD alerts
│   │   └── rules.yml
│   │
│   ├── grafana/
│   │   ├── dashboards/
│   │   │   ├── bft-consensus.json
│   │   │   ├── mtd-operations.json
│   │   │   └── system-performance.json
│   │   └── provisioning/
│   │
│   └── wazuh/
│       ├── custom_rules.xml    # BFT/MTD rules
│       └── decoders/
│
├── vault/
│   ├── config.hcl              # Vault configuration
│   └── policies/               # Access policies
│
├── scripts/
│   ├── init-vault.sh           # Initialize Vault
│   ├── check-cluster.sh        # BFT cluster health
│   ├── trigger-rotation.sh     # Manual MTD rotation
│   ├── inject-byzantine-fault.sh
│   ├── simulate-attack.sh
│   └── create-partition.sh
│
├── tests/
│   ├── test_bft.py             # BFT unit tests
│   ├── test_mtd.py             # MTD unit tests
│   └── integration/
│       ├── test_order_creation.py
│       └── test_fault_tolerance.py
│
├── report/
│   ├── main.tex                # LaTeX report
│   ├── sections/
│   ├── figures/
│   └── references.bib
│
├── docker-compose.yml          # Main deployment
├── docker-compose.integrated.yml # With Project 1
├── .env.example
├── .gitignore
└── README.md                   # This file
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
