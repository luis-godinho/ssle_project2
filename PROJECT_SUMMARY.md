# Project Summary - SSLE Project 2

## 🎯 What Has Been Created

Your **ssle_project2** repository is now initialized with:

### 1. Core Documentation
- ✅ **README.md** - Complete project documentation with:
  - Architecture diagrams
  - Byzantine Fault Tolerance explanation
  - Moving Target Defense explanation
  - Risk management analysis
  - Testing scenarios
  - Integration with Project 1
  - Deployment instructions

- ✅ **docker-compose.yml** - Full infrastructure with:
  - Service Registry (MTD coordinator)
  - 3-node Order Service BFT cluster
  - Product/Payment/Email services with MTD
  - API Gateway with load balancing
  - Wazuh security monitoring
  - Prometheus + Grafana
  - HashiCorp Vault for secrets

- ✅ **IMPLEMENTATION_GUIDE.md** - Detailed code examples for:
  - Service Registry with MTD port allocation
  - BFT Consensus module
  - Order Service with consensus voting
  - Service structure and patterns

---

## 🛠️ What You Need to Implement

### Phase 1: Core Services (from Project 1)

Copy and adapt these from your **ssle_project1**:

1. **Product Service**
   - Copy from Project 1
   - Add MTD rotation client (see IMPLEMENTATION_GUIDE.md)
   - Register with Registry on startup
   - Rotate ports every 5 minutes

2. **Payment Service**
   - Copy from Project 1
   - Add MTD rotation client
   - Same pattern as Product Service

3. **Email Service**
   - Copy from Project 1
   - Add MTD rotation for SMTP ports
   - Keep spam filtering capabilities

4. **API Gateway**
   - Copy from Project 1
   - Add load balancing to Order Service cluster
   - Add MTD rotation
   - Keep DoS protection

5. **Web Service**
   - Copy from Project 1
   - Update to use dynamic Registry discovery
   - Keep Shellshock monitoring

### Phase 2: New Implementations

6. **Service Registry** - ✅ Code provided in IMPLEMENTATION_GUIDE.md
   - Port allocation logic
   - Service discovery
   - MTD coordination

7. **Order Service BFT Cluster** - ✅ Code provided
   - Consensus module
   - 3-node cluster
   - Vote-based operations

### Phase 3: Monitoring & Security

8. **Wazuh Custom Rules**
   ```xml
   <!-- Byzantine behavior detection -->
   <rule id="100200" level="12">
     <match>vote_mismatch</match>
     <description>Byzantine fault detected</description>
   </rule>
   
   <!-- Quorum loss -->
   <rule id="100201" level="14">
     <match>quorum_lost</match>
     <description>Critical: BFT quorum lost</description>
   </rule>
   
   <!-- MTD rotation anomaly -->
   <rule id="100210" level="8">
     <match>rotation_failed</match>
     <description>MTD rotation failed</description>
   </rule>
   ```

9. **Prometheus Configuration**
   ```yaml
   scrape_configs:
     - job_name: 'order-cluster'
       static_configs:
         - targets: 
           - 'order-node-1:8002'
           - 'order-node-2:8012'
           - 'order-node-3:8022'
     
     - job_name: 'services-mtd'
       consul_sd_configs:
         - server: 'registry:5000'
   ```

10. **Grafana Dashboards**
    - BFT Consensus dashboard
    - MTD Operations dashboard
    - Service Health dashboard

### Phase 4: Testing

11. **Test Scripts**
    ```bash
    # scripts/test-bft.sh
    # Test Byzantine fault tolerance
    
    # scripts/test-mtd.sh
    # Test port rotation
    
    # scripts/simulate-attack.sh
    # Combined attack scenario
    ```

12. **Unit Tests**
    - BFT consensus tests
    - MTD rotation tests
    - Integration tests

### Phase 5: Report

13. **LaTeX Report** with sections:
    - Introduction
    - Service Architecture
    - Risk Management (Byzantine faults, Reconnaissance)
    - BFT Approach
    - MTD Approach
    - Evaluation
    - Conclusions

---

## 🚀 Quick Start Guide

### Step 1: Clone and Setup

```bash
# Clone your new project
git clone https://github.com/luis-godinho/ssle_project2.git
cd ssle_project2

# Create directory structure
mkdir -p services/{registry,order-service,product-service,payment-service,email-service,api-gateway,web-service}
mkdir -p monitoring/{prometheus,grafana/{dashboards,provisioning},alertmanager}
mkdir -p wazuh/{config,custom_rules}
mkdir -p vault/{config,policies}
mkdir -p scripts tests
```

### Step 2: Copy from Project 1

```bash
# From your ssle_project1 directory, copy:
cp -r services/product-service/* ../ssle_project2/services/product-service/
cp -r services/payment-service/* ../ssle_project2/services/payment-service/
cp -r services/email-service/* ../ssle_project2/services/email-service/
cp -r services/api-gateway/* ../ssle_project2/services/api-gateway/
cp -r services/web-service/* ../ssle_project2/services/web-service/

# Copy monitoring configs
cp -r monitoring/* ../ssle_project2/monitoring/
cp -r wazuh/* ../ssle_project2/wazuh/
```

### Step 3: Implement New Components

Use the code from **IMPLEMENTATION_GUIDE.md**:

```bash
# Create Service Registry
cd services/registry
# Copy code from IMPLEMENTATION_GUIDE.md

# Create Order Service BFT
cd ../order-service
# Copy consensus.py and app.py from IMPLEMENTATION_GUIDE.md
```

### Step 4: Add MTD to Existing Services

For each service (Product, Payment, Email, Gateway), add:

```python
# mtd_client.py
import requests
import time
import threading
import os

class MTDClient:
    def __init__(self, service_name, registry_url, initial_port, port_range):
        self.service_name = service_name
        self.registry_url = registry_url
        self.current_port = initial_port
        self.port_range = port_range
        self.rotation_interval = 300  # 5 minutes
        
    def start_rotation(self):
        """Start MTD rotation thread"""
        thread = threading.Thread(target=self._rotation_loop, daemon=True)
        thread.start()
        
    def _rotation_loop(self):
        while True:
            time.sleep(self.rotation_interval)
            self._rotate_port()
            
    def _rotate_port(self):
        # Request new port from registry
        # Start service on new port
        # Drain old port connections
        # Update registry
        pass
```

### Step 5: Test Locally

```bash
# Start everything
docker-compose up -d

# Check cluster status
curl http://localhost:8002/consensus/status

# Test order creation (triggers consensus)
curl -X POST http://localhost:8080/proxy/order-service/api/orders \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "CUST001", "items": [{"product_id": "PROD001", "quantity": 1}]}'

# Check service rotations
curl http://localhost:5000/services
```

---

## 📊 Key Differences from Project 1

| Aspect | Project 1 | Project 2 |
|--------|-----------|----------|
| **Focus** | Threat Detection | Attack Tolerance |
| **Architecture** | Single service instances | BFT cluster + MTD |
| **Order Service** | 1 instance | 3 instances (consensus) |
| **Service Ports** | Fixed | Dynamic (MTD rotation) |
| **Service Discovery** | Static | Dynamic via Registry |
| **Security** | Detect attacks | Tolerate attacks |
| **Main Goal** | Monitor threats | Continue operating during attacks |

---

## ✅ Project Deliverables Checklist

### Code (50%)
- [ ] Service Registry with MTD
- [ ] Order Service BFT cluster (3 nodes)
- [ ] Product/Payment/Email services with MTD
- [ ] API Gateway with load balancing
- [ ] Wazuh custom rules for BFT/MTD
- [ ] Prometheus metrics for tolerance
- [ ] Grafana dashboards
- [ ] Docker Compose deployment
- [ ] Test scripts

### Report (50%)
- [ ] Introduction
- [ ] Service Architecture description
- [ ] Risk Management analysis (2 faults)
- [ ] Byzantine Fault Tolerance approach
- [ ] Moving Target Defense approach
- [ ] Evaluation (performance, scalability, effectiveness)
- [ ] Conclusions

### Bonus (+3)
- [ ] Integration with Project 1
- [ ] Combined threat detection + tolerance
- [ ] Unified monitoring dashboard

---

## 🎯 Evaluation Criteria

### Effectiveness
- Does BFT cluster maintain quorum with 1 failed node? ✅
- Do services continue operating during MTD rotation? ✅
- Are Byzantine behaviors detected and rejected? ✅
- Does attack reconnaissance become ineffective? ✅

### Scalability
- Can cluster handle normal load? ✅
- What's the consensus overhead? (measure with Prometheus)
- What's the MTD rotation overhead? (measure latency)
- How does it scale to more nodes? (theory in report)

### Security
- Byzantine node cannot corrupt system ✅
- Attacker cannot map architecture due to MTD ✅
- Wazuh detects anomalies ✅

---

## 📅 Timeline Suggestion

**Total: ~40-50 hours of work**

- **Days 1-2**: Copy Project 1 services, adapt for MTD (10h)
- **Days 3-4**: Implement Service Registry and BFT (12h)
- **Days 5-6**: Testing and debugging (10h)
- **Days 7-8**: Monitoring dashboards and Wazuh rules (8h)
- **Days 9-12**: Report writing (15h)
- **Day 13**: Demo video preparation (3h)
- **Day 14**: Final review and submission (2h)

---

## 🔗 Resources

### Documentation
- [Byzantine Fault Tolerance (Castro & Liskov)](http://pmg.csail.mit.edu/papers/osdi99.pdf)
- [Moving Target Defense Overview](https://www.sciencedirect.com/science/article/pii/S0167404814000054)
- [Consensus Algorithms](https://raft.github.io/)

### Your Repositories
- **Project 1**: [ssle_project1](https://github.com/luis-godinho/ssle_project1)
- **Project 2**: [ssle_project2](https://github.com/luis-godinho/ssle_project2) ⭐ **YOU ARE HERE**

### Tools
- Docker Compose
- Wazuh Documentation
- Prometheus + Grafana
- HashiCorp Vault

---

## ❓ FAQ

**Q: Can I modify Project 1 instead of creating Project 2?**
A: The professor offers +3 bonus for integration, implying separate projects. Keep them separate for clarity.

**Q: Do I need to implement both BFT and MTD?**
A: Yes, you need 2 attack tolerance mechanisms from the syllabus.

**Q: What if I want different mechanisms?**
A: You can choose any 2 from: BFT, MTD, Anomaly Detection, Supply Chain Security, Secret Distribution. Confirm with supervisor.

**Q: How do I prove it works?**
A: Tests that show:
1. BFT: Stop 1 node → system works; inject false data → rejected
2. MTD: Port scan before/after → different ports; requests still work

**Q: What about the report?**
A: Follow structure in Project 2 requirements PDF. Focus on **why** the mechanisms work and **how** you evaluated them.

---

## 👥 Support

If you need help:
1. Check IMPLEMENTATION_GUIDE.md for code examples
2. Review README.md for architecture details
3. Look at Project 1 for service patterns
4. Test incrementally (one service at a time)

---

## 🎉 Summary

**You now have**:
- ✅ Complete project architecture designed
- ✅ Docker Compose infrastructure ready
- ✅ Code examples for core components
- ✅ Clear implementation roadmap
- ✅ Testing strategy
- ✅ Evaluation criteria

**Next steps**:
1. Copy services from Project 1
2. Implement Service Registry (code provided)
3. Implement Order Service BFT (code provided)
4. Add MTD to existing services
5. Configure monitoring
6. Test everything
7. Write report
8. Create demo video
9. Submit!

**Good luck! 🚀**
