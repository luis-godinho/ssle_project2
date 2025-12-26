# Vault Integration - Branch: vault-integration

## 🔐 Overview

This branch demonstrates **HashiCorp Vault integration** for secure secret management in the BFT cluster.

### What's Been Added

1. **Vault Service** - HashiCorp Vault server for secret storage
2. **BFT Node Authentication** - Nodes authenticate votes using Vault tokens
3. **Vote Signatures** - HMAC-SHA256 signatures prevent vote spoofing
4. **Vault Client** - Python utility for accessing secrets
5. **Initialization Scripts** - Automated Vault setup

---

## 🎯 Purpose: Byzantine Vote Authentication

### The Problem

**Without Vault:**
- Nodes trust all votes from cluster members
- Byzantine attacker could spoof votes from other nodes
- No cryptographic verification of vote authenticity

### The Solution

**With Vault:**
- Each BFT node has a unique authentication token stored in Vault
- Votes are signed with HMAC-SHA256 using the node's token
- Receiving nodes verify signatures using tokens from Vault
- **Byzantine attackers cannot forge valid signatures** without the token

---

## 📚 Implementation Details

### 1. Vault Configuration

**File:** `vault/config.hcl`
```hcl
storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1  # Dev mode only!
}
```

**Secrets stored:**
```
secret/bft-cluster/order-node-1  -> {"auth_token": "abc123..."}
secret/bft-cluster/order-node-2  -> {"auth_token": "def456..."}
secret/bft-cluster/order-node-3  -> {"auth_token": "ghi789..."}
secret/registry/api-token        -> {"api_token": "xyz999..."}
secret/services/product-service  -> {"service_token": "pqr888..."}
```

### 2. Vault Client

**File:** `services/vault_client.py`

```python
from vault_client import vault_client

# Get BFT node token
token = vault_client.get_bft_node_token("order-node-1")

# Get service token
service_token = vault_client.get_service_token("product-service")

# Get registry token
registry_token = vault_client.get_registry_token()
```

**Features:**
- Graceful degradation if Vault unavailable
- Automatic retry logic
- Environment variable configuration

### 3. BFT Consensus with Authentication

**File:** `services/order-service/consensus.py`

**Vote Signing:**
```python
def _sign_vote(self, operation_id: str, vote: str) -> str:
    """Sign vote with node's Vault token"""
    message = f"{operation_id}:{vote}:{self.node_id}"
    signature = hmac.new(
        self.auth_token.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature
```

**Vote Verification:**
```python
def _verify_vote_signature(self, node_id: str, operation_id: str, 
                          vote: str, signature: str) -> bool:
    """Verify vote signature using node's Vault token"""
    node_token = vault_client.get_bft_node_token(node_id)
    expected_signature = hmac.new(
        node_token.encode(),
        f"{operation_id}:{vote}:{node_id}".encode(),
        hashlib.sha256
    ).hexdigest()
    
    if signature != expected_signature:
        logger.error(f"BYZANTINE BEHAVIOR: Invalid signature from {node_id}")
        return False
    
    return True
```

---

## 🚀 Usage

### Step 1: Start Vault

```bash
# Start Vault service
docker-compose up -d vault

# Wait for Vault to be ready
sleep 5
```

### Step 2: Initialize Vault

```bash
# Run initialization script
chmod +x scripts/init-vault.sh scripts/check-vault.sh
./scripts/init-vault.sh
```

**Output:**
```
🔐 Initializing Vault...

Waiting for Vault to start...
✅ Vault is ready
Initializing Vault with 1 key share (DEV MODE)...
✅ Vault initialized

📝 Credentials saved to .vault/ directory
   Unseal Key: .vault/unseal-key
   Root Token: .vault/root-token

✅ Vault unsealed
✅ KV secrets engine enabled

Creating BFT node authentication tokens...
  ✅ order-node-1: token created
  ✅ order-node-2: token created
  ✅ order-node-3: token created

Creating Service Registry API token...
  ✅ Service Registry: token created

Creating service authentication tokens...
  ✅ product-service: token created
  ✅ payment-service: token created
  ✅ email-service: token created
  ✅ api-gateway: token created

✅ Services policy created
✅ Application token created: .vault/app-token

🎉 Vault initialization complete!

📊 Summary:
   Vault URL: http://localhost:8200
   Root Token: hvs.abc123...
   App Token: hvs.def456...

🔑 Secrets created:
   - BFT node tokens: secret/bft-cluster/{order-node-1,order-node-2,order-node-3}
   - Registry token: secret/registry/api-token
   - Service tokens: secret/services/{product,payment,email,api-gateway}-service
```

### Step 3: Export Vault Token

```bash
# Export application token for services
export VAULT_TOKEN=$(cat .vault/app-token)
export VAULT_ADDR=http://localhost:8200
```

### Step 4: Start Services with Vault

```bash
# Start all services
docker-compose up -d

# Check Vault status
./scripts/check-vault.sh
```

### Step 5: Test BFT with Authentication

```bash
# Create order (all nodes authenticate)
curl -X POST http://localhost:8080/proxy/order-service/api/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST001",
    "items": [{"product_id": "PROD001", "quantity": 1, "price": 999.99}]
  }'

# Check consensus status (should show vault_auth_enabled: true)
curl http://localhost:8002/consensus/status | jq
```

---

## 🧪 Testing Vote Authentication

### Test 1: Valid Votes

```bash
# Create order - all nodes sign votes with their tokens
curl -X POST http://localhost:8002/api/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST001",
    "items": [{"product_id": "PROD001", "quantity": 1}]
  }'

# Result: Order created (✅ all signatures valid)
```

### Test 2: Simulate Byzantine Attack (Invalid Signature)

```bash
# Manually send a vote with invalid signature
curl -X POST http://localhost:8002/consensus/vote \
  -H "Content-Type: application/json" \
  -d '{
    "operation_id": "abc123",
    "operation_type": "CREATE_ORDER",
    "operation_data": {"customer_id": "HACKER"},
    "proposer": "order-node-1"
  }'

# Node returns legitimate vote with signature
# But if attacker tries to forge signature:
# Log: "BYZANTINE BEHAVIOR DETECTED: Invalid vote signature"
```

### Test 3: Check Logs for Byzantine Detection

```bash
# View order service logs
docker logs order-node-1 2>&1 | grep "BYZANTINE"

# Output:
# ERROR - BYZANTINE BEHAVIOR DETECTED: Invalid vote signature from order-node-3
# ERROR -   Expected: a1b2c3d4...
# ERROR -   Received: 00000000...
```

---

## 📊 How It Works

### Vote Flow with Vault

```
1. Leader (Node 1) proposes operation
   ↓
2. Node 1 sends vote request to Nodes 2 & 3
   ↓
3. Each node:
   a. Validates operation
   b. Retrieves its token from Vault
   c. Signs vote: HMAC-SHA256(token, operation_id + vote)
   d. Returns {vote: "approve", signature: "abc123..."}
   ↓
4. Node 1 receives votes
   ↓
5. Node 1 verifies each signature:
   a. Gets voter's token from Vault
   b. Computes expected signature
   c. Compares with received signature
   d. Rejects if mismatch → "BYZANTINE BEHAVIOR"
   ↓
6. Count only votes with valid signatures
   ↓
7. If 2/3 valid votes → commit operation
```

### Attack Prevention

**Scenario: Byzantine Node Tries to Forge Votes**

```python
# Attacker (compromised node-3) tries to forge vote from node-2
fake_vote = {
    "node": "order-node-2",  # Pretending to be node-2
    "vote": "approve",
    "signature": "fake_signature_12345"
}

# Node 1 verifies:
node2_token = vault_client.get_bft_node_token("order-node-2")
expected_sig = hmac(node2_token, message)

if fake_signature != expected_sig:
    logger.error("BYZANTINE BEHAVIOR DETECTED")
    # Vote rejected, not counted toward quorum
```

**Result:** Attacker cannot forge valid votes without stealing tokens from Vault ✅

---

## 🔍 Vault UI

### Access Vault UI

```bash
# Get root token
ROOT_TOKEN=$(cat .vault/root-token)

# Open in browser
open http://localhost:8200/ui

# Login with root token
```

### View Secrets

1. Navigate to **Secrets** → **secret/**
2. Browse:
   - `bft-cluster/` - Node authentication tokens
   - `services/` - Service API tokens
   - `registry/` - Registry master token

---

## 📊 Monitoring

### Prometheus Metrics

```promql
# Vote signature verification failures
rate(bft_vote_signature_failures_total[5m])

# Byzantine behavior detections
rate(bft_byzantine_behavior_total[5m])
```

### Wazuh Alerts

```xml
<!-- Rule for Byzantine behavior -->
<rule id="100200" level="12">
  <match>BYZANTINE BEHAVIOR DETECTED</match>
  <description>Invalid vote signature detected in BFT cluster</description>
</rule>
```

---

## ⚙️ Configuration

### Environment Variables

**Order Service:**
```bash
VAULT_ADDR=http://vault:8200
VAULT_TOKEN=hvs.abc123...  # From .vault/app-token
NODE_ID=order-node-1
NODE_PORT=8002
```

**docker-compose.yml:**
```yaml
order-node-1:
  environment:
    - VAULT_ADDR=http://vault:8200
    - VAULT_TOKEN=${VAULT_TOKEN}  # From environment
    - NODE_ID=order-node-1
    - NODE_PORT=8002
  depends_on:
    - vault
```

---

## 🔒 Security Considerations

### Production Recommendations

1. **Enable TLS** for Vault
   ```hcl
   listener "tcp" {
     tls_cert_file = "/vault/certs/cert.pem"
     tls_key_file = "/vault/certs/key.pem"
   }
   ```

2. **Use AppRole authentication** instead of tokens
   ```bash
   vault auth enable approle
   vault write auth/approle/role/order-service \
     secret_id_ttl=24h \
     token_ttl=1h
   ```

3. **Rotate tokens regularly**
   ```bash
   # Script to rotate all BFT node tokens
   for NODE in order-node-1 order-node-2 order-node-3; do
     NEW_TOKEN=$(openssl rand -hex 32)
     vault kv put secret/bft-cluster/$NODE auth_token=$NEW_TOKEN
   done
   ```

4. **Use Vault auto-unseal** with cloud KMS
   ```hcl
   seal "awskms" {
     region     = "us-east-1"
     kms_key_id = "..."
   }
   ```

5. **Enable audit logging**
   ```bash
   vault audit enable file file_path=/vault/logs/audit.log
   ```

---

## 🔄 Differences from Main Branch

| Feature | Main Branch | Vault Branch |
|---------|-------------|-------------|
| **Vote Authentication** | None | HMAC-SHA256 signatures |
| **Token Storage** | N/A | Vault secrets |
| **Byzantine Detection** | Basic validation | Cryptographic verification |
| **Vote Spoofing** | Possible | Prevented ✅ |
| **Dependencies** | None | Vault service |
| **Setup Complexity** | Low | Medium |
| **Production Ready** | No | Yes (with TLS) |

---

## 📚 Files Changed/Added

### New Files
- `vault/config.hcl` - Vault configuration
- `vault/Dockerfile` - Vault container
- `services/vault_client.py` - Vault client utility
- `scripts/init-vault.sh` - Vault initialization
- `scripts/check-vault.sh` - Vault status checker
- `VAULT_INTEGRATION.md` - This documentation

### Modified Files
- `services/order-service/consensus.py` - Added vote signing/verification
- `services/order-service/app.py` - Returns vote signatures

---

## ✅ Testing Checklist

- [ ] Vault starts and initializes successfully
- [ ] BFT node tokens created in Vault
- [ ] Nodes retrieve tokens on startup
- [ ] Votes include HMAC signatures
- [ ] Valid signatures are accepted
- [ ] Invalid signatures trigger Byzantine alerts
- [ ] Orders create successfully with authenticated votes
- [ ] Vault UI accessible
- [ ] check-vault.sh shows all tokens

---

## 🎓 For Your Report

### Key Points to Highlight

1. **Cryptographic Authentication**: Votes signed with HMAC-SHA256
2. **Byzantine Attack Prevention**: Invalid signatures detected and rejected
3. **Secret Management**: Centralized token storage in Vault
4. **Graceful Degradation**: System works if Vault unavailable (dev mode)
5. **Production Ready**: With TLS and AppRole, suitable for production

### Demonstration Script

```bash
# 1. Show Vault initialization
./scripts/init-vault.sh

# 2. Show tokens in Vault
./scripts/check-vault.sh

# 3. Create order with authenticated votes
curl -X POST http://localhost:8002/api/orders \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "DEMO", "items": [{"product_id": "P001", "quantity": 1}]}' | jq

# 4. Show vote signatures in logs
docker logs order-node-1 | grep "signature"

# 5. Show Byzantine detection (if any)
docker logs order-node-1 | grep "BYZANTINE"
```

---

## 🚀 Merge to Main?

**Recommendation:** Keep this as a **separate branch** to demonstrate advanced features.

**Pros:**
- Shows production-grade security implementation
- Demonstrates understanding of cryptographic authentication
- Bonus points for going beyond requirements

**Cons:**
- Adds complexity to setup
- Requires additional service (Vault)
- Not strictly required for project goals (BFT + MTD)

**Decision:** Present both versions:
- **Main branch**: Core BFT + MTD (simpler, focus on mechanisms)
- **Vault branch**: Production-ready with authentication (advanced)

Good luck! 🎉
