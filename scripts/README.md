# 🧪 Security Testing Suite

Comprehensive test scripts for demonstrating all security features of the Secure E-Commerce Platform.

## 📋 Available Tests

---

### **test-mtd.sh** - Moving Target Defense

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

---

### **test-bft.sh** - Byzantine Fault Tolerance

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

---
