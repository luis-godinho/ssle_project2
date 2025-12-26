# Changes from Project 1 to Project 2

This document explains what was added/changed from **ssle_project1** to **ssle_project2** to implement Attack Tolerance Mechanisms.

---

## 🆕 NEW Services Added

### 1. Service Registry (`services/registry/`)
**Purpose**: Central coordinator for Moving Target Defense (MTD)

**Files:**
- `app.py` - Registry with dynamic port allocation
- `Dockerfile`
- `requirements.txt`

**Features:**
- Service registration and discovery
- Dynamic port allocation for MTD
- Health monitoring via heartbeats
- Port rotation management
- Tracks all service locations

**Endpoints:**
- `POST /register` - Register service
- `GET /discover/<service>` - Find current service location
- `GET /services` - List all services
- `POST /rotate/<service>` - Trigger port rotation
- `POST /heartbeat/<service>` - Receive heartbeat

**Port:** 5000

---

### 2. Order Service with BFT (`services/order-service/`)
**Purpose**: Byzantine Fault Tolerant order processing cluster

**Files:**
- `app.py` - Order service with consensus
- `consensus.py` - BFT consensus protocol implementation
- `Dockerfile`
- `requirements.txt`

**Features:**
- **3-node cluster** (order-node-1, order-node-2, order-node-3)
- **BFT consensus** for all operations
- **Quorum-based decisions** (2/3 agreement required)
- **State replication** across nodes
- **Vote validation** for each operation
- **Byzantine behavior detection**

**Consensus Operations:**
- `CREATE_ORDER` - Requires 2/3 votes
- `UPDATE_STATUS` - Requires 2/3 votes
- `CANCEL_ORDER` - Requires 2/3 votes

**Endpoints (per node):**
- `POST /api/orders` - Create order (triggers consensus)
- `GET /api/orders/<id>` - Get order
- `PUT /api/orders/<id>/status` - Update status (triggers consensus)
- `POST /consensus/vote` - Vote on operation
- `GET /consensus/status` - Cluster health

**Ports:**
- Node 1: 8002
- Node 2: 8012
- Node 3: 8022

---

### 3. Product Service (NEW Implementation)
**Purpose**: Product catalog with MTD rotation

**Changes from Project 1:**
- ✅ Added MTD registration with Service Registry
- ✅ Added periodic heartbeat to registry
- ✅ Ready for dynamic port rotation
- ✅ Exposes current port in responses

**Port Range:** 8001-8011 (MTD rotation)

---

## 🔄 Modified Services

### API Gateway (`services/api-gateway/`)
**Status:** Needs update for MTD

**Current (Project 1):**
- Fixed routing to backend services
- DDoS detection
- Rate limiting

**Needed for Project 2:**
- ⚠️ Service discovery via Registry
- ⚠️ Dynamic routing to current ports
- ⚠️ MTD registration and rotation

**Changes needed in `app.py`:**
```python
# OLD (Project 1):
PRODUCT_SERVICE_URL = "http://product-service:8001"

# NEW (Project 2):
def get_service_url(service_name):
    response = requests.get(f"{REGISTRY_URL}/discover/{service_name}")
    return response.json()["url"]
```

---

### Payment Service (`services/payment-service/`)
**Status:** Needs MTD integration

**Needed:**
- ⚠️ Register with Service Registry on startup
- ⚠️ Send periodic heartbeats
- ⚠️ Handle port rotation

---

### Email Service (`services/email-service/`)
**Status:** Needs MTD integration

**Needed:**
- ⚠️ Register with Service Registry
- ⚠️ Periodic heartbeats
- ⚠️ MTD rotation capability

---

### Web Service (`services/web-service/`)
**Status:** Can stay as-is

**Note:** Web service typically doesn't rotate (user-facing), but it should use API Gateway which handles service discovery.

---

## 🐛 What Still Needs to Be Done

### Priority 1: Update API Gateway
The API Gateway needs to discover services dynamically instead of using fixed URLs.

**File:** `services/api-gateway/app.py`

**Changes:**
```python
# Add at top
REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://registry:5000")

# Update proxy_request function
@app.route("/proxy/<service_name>/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy_request(service_name, path):
    try:
        # Discover service from registry
        response = requests.get(f"{REGISTRY_URL}/discover/{service_name}", timeout=5)
        
        if response.status_code != 200:
            return jsonify({"error": f"Service {service_name} not found"}), 404
        
        service_info = response.json()
        service_url = service_info["url"]
        
        # Forward request to discovered URL
        target_url = f"{service_url}/{path}"
        # ... rest of forwarding logic
```

### Priority 2: Add MTD to Payment Service
**File:** `services/payment-service/app.py`

**Add registration:**
```python
def register_with_registry():
    """Register with service registry"""
    requests.post(
        f"{REGISTRY_URL}/register",
        json={
            "name": "payment-service",
            "host": "payment-service",
            "port": SERVICE_PORT,
        },
    )

# In main:
registration_thread = Thread(target=register_with_registry, daemon=True)
registration_thread.start()
```

### Priority 3: Add MTD to Email Service
Same pattern as Payment Service.

---

## 📊 Monitoring Updates

### Prometheus (`monitoring/prometheus/`)
**New metrics to scrape:**
```yaml
# prometheus.yml
scrape_configs:
  # NEW - Service Registry
  - job_name: 'registry'
    static_configs:
      - targets: ['registry:5000']
  
  # NEW - Order Service Cluster
  - job_name: 'order-service'
    static_configs:
      - targets: 
        - 'order-node-1:8002'
        - 'order-node-2:8012'
        - 'order-node-3:8022'
```

**New metrics available:**
- `registry_services_total` - Total registered services
- `registry_rotations_total` - Port rotations by service
- `order_consensus_proposals_total` - Consensus proposals
- `order_consensus_approved_total` - Approved operations
- `order_cluster_quorum_available` - Quorum status

### Wazuh (`wazuh/`)
**New rules needed:**
```xml
<!-- Byzantine behavior detection -->
<rule id="100200" level="12">
  <match>vote_mismatch</match>
  <description>Byzantine fault detected in BFT cluster</description>
</rule>

<!-- MTD rotation alerts -->
<rule id="100210" level="5">
  <match>Rotation requested</match>
  <description>MTD port rotation triggered</description>
</rule>
```

---

## 🐳 Docker Compose Changes

### New Services in `docker-compose.yml`

```yaml
# Service Registry
registry:
  build: ./services/registry
  ports:
    - "5000:5000"
  networks:
    - ecommerce-network

# Order Service - Node 1
order-node-1:
  build: ./services/order-service
  environment:
    - NODE_ID=order-node-1
    - NODE_PORT=8002
    - CLUSTER_NODES=http://order-node-1:8002,http://order-node-2:8012,http://order-node-3:8022
  ports:
    - "8002:8002"

# Order Service - Node 2
order-node-2:
  build: ./services/order-service
  environment:
    - NODE_ID=order-node-2
    - NODE_PORT=8012
    - CLUSTER_NODES=http://order-node-1:8002,http://order-node-2:8012,http://order-node-3:8022
  ports:
    - "8012:8012"

# Order Service - Node 3
order-node-3:
  build: ./services/order-service
  environment:
    - NODE_ID=order-node-3
    - NODE_PORT=8022
    - CLUSTER_NODES=http://order-node-1:8002,http://order-node-2:8012,http://order-node-3:8022
  ports:
    - "8022:8022"

# Product Service (updated with MTD)
product-service:
  build: ./services/product-service
  environment:
    - SERVICE_PORT=8001
    - REGISTRY_URL=http://registry:5000
    - MTD_ENABLED=true
  ports:
    - "8001-8011:8001-8011"  # Port range for MTD
```

---

## ✅ Testing Checklist

### BFT Tests
- [ ] All 3 nodes start successfully
- [ ] Create order with 3/3 nodes (should succeed)
- [ ] Stop node-2, create order with 2/3 nodes (should succeed) ← **KEY TEST**
- [ ] Stop 2 nodes, create order with 1/3 nodes (should fail)
- [ ] Restart node-2, verify it rejoins cluster
- [ ] Check Prometheus metrics for consensus votes

### MTD Tests
- [ ] Services register with Registry on startup
- [ ] Registry shows all services with current ports
- [ ] Trigger manual rotation: `curl -X POST http://localhost:5000/rotate/product-service`
- [ ] Verify service moves to new port
- [ ] Make request via API Gateway (should work automatically)
- [ ] Port scan shows different ports over time

### Integration Tests
- [ ] Create order via Gateway → triggers BFT consensus
- [ ] Order service queries product service via Registry
- [ ] All services send heartbeats to Registry
- [ ] Monitoring captures all BFT and MTD metrics

---

## 🚀 Quick Start

```bash
# 1. Enter Nix environment
nix develop

# 2. Start everything
start-project

# 3. Check cluster health
check-cluster

# Expected output:
# ✅ Docker is running
# ✅ BFT Cluster Status: 3/3 nodes healthy
# ✅ MTD Service Registry: 4 services registered

# 4. Test BFT
test-bft

# 5. Test MTD
test-mtd
```

---

## 📚 Key Files for Review

### Core Implementation
1. **`services/registry/app.py`** - MTD coordinator
2. **`services/order-service/consensus.py`** - BFT consensus protocol
3. **`services/order-service/app.py`** - Order service with consensus
4. **`services/product-service/app.py`** - Example MTD-enabled service

### Documentation
1. **`IMPLEMENTATION_GUIDE.md`** - Detailed code explanations
2. **`TESTING_GUIDE.md`** - Comprehensive testing instructions
3. **`README.md`** - Project overview
4. **`PROJECT_SUMMARY.md`** - Quick reference

### Configuration
1. **`docker-compose.yml`** - Updated with new services
2. **`flake.nix`** - Nix development environment

---

## 🔑 Key Differences Summary

| Aspect | Project 1 | Project 2 |
|--------|-----------|----------|
| **Order Service** | Single instance | 3-node BFT cluster |
| **Service Discovery** | Fixed URLs | Dynamic via Registry |
| **Port Management** | Static ports | Dynamic MTD rotation |
| **Fault Tolerance** | None | Byzantine faults (1 node) |
| **Attack Defense** | Detection only | Tolerance (BFT + MTD) |
| **Consensus** | N/A | 2/3 quorum required |
| **Service Registry** | None | Central MTD coordinator |

---

## ⚠️ Important Notes

1. **Project 1 services (payment, email, web) still work** - they just need MTD integration
2. **API Gateway needs update** to use service discovery
3. **BFT cluster requires 2/3 nodes** to be operational
4. **MTD rotation is optional** but demonstrates the mechanism
5. **Monitoring integration** shows both threat detection (P1) and tolerance (P2)

---

## 🎓 For Your Report

**Highlight these points:**

1. ✅ **BFT Implementation**: 3-node consensus cluster tolerates 1 Byzantine fault
2. ✅ **MTD Implementation**: Dynamic port rotation defeats reconnaissance
3. ✅ **Service Registry**: Central coordinator for MTD
4. ✅ **Integration**: Project 1 threat detection + Project 2 attack tolerance
5. ✅ **Evaluation**: Automated testing via Nix flake
6. ✅ **Monitoring**: Prometheus/Grafana/Wazuh track all mechanisms

Good luck! 🚀
