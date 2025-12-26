# SSLE Project 2 - Quick Start Guide

## Overview

This is a comprehensive secure e-commerce system integrating:
- **Byzantine Fault Tolerant (BFT) Consensus** for order service cluster
- **Moving Target Defense (MTD)** for dynamic port rotation
- **HashiCorp Vault** for secret management
- **Wazuh** for security monitoring and alerting
- **Prometheus + Grafana** for system monitoring

## Prerequisites

- Docker & Docker Compose (v3.8+)
- 8GB+ RAM recommended
- Linux/macOS (Windows with WSL2)
- `curl` and `jq` for initialization scripts

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd ssle_project2
git checkout vault-integration
```

### 2. Start All Services

```bash
docker-compose up -d
```

This will start:
- All 3 order service nodes (BFT cluster)
- Product, Payment, Email services (with MTD)
- API Gateway with load balancing
- Web service
- Vault (secrets management)
- Wazuh stack (security monitoring)
- Prometheus + Grafana (metrics)

### 3. Initialize Vault

```bash
# Wait for Vault to be ready (30-60 seconds)
sleep 60

# Run initialization script
./scripts/init-vault.sh
```

This creates:
- Unseal keys and root token
- Service authentication tokens
- BFT node credentials
- Application policies

Tokens are saved to `.vault/` directory (add to `.gitignore`)

### 4. Verify Services

```bash
# Check Vault status
curl http://localhost:8200/v1/sys/health | jq .

# Check all containers
docker-compose ps

# View logs
docker-compose logs -f [service-name]
```

## Service Endpoints

| Service | URL | Port |
|---------|-----|------|
| Web UI | http://localhost | 80 |
| API Gateway | http://localhost:8080 | 8080-8090 (MTD) |
| Service Registry | http://localhost:5000 | 5000 |
| Vault | http://localhost:8200 | 8200 |
| Vault UI | http://localhost:8200/ui | 8200 |
| Prometheus | http://localhost:9090 | 9090 |
| Grafana | http://localhost:3000 | 3000 |
| Wazuh Dashboard | https://localhost:443 | 443 |

### Credentials

**Grafana:**
- Username: `admin`
- Password: `admin`

**Wazuh Dashboard:**
- Username: `admin`
- Password: `SecretPassword`
- API User: `wazuh-wui`
- API Password: `MyS3cr37P450r.*-`

**Vault (after init-vault.sh):**
- Root Token: Check `.vault/root-token`
- Token Path: `http://localhost:8200/ui`

## Architecture

### BFT Order Service Cluster

Three order service nodes running Byzantine Fault Tolerant consensus:
- **order-node-1**: Port 8102 (primary)
- **order-node-2**: Port 8112
- **order-node-3**: Port 8122

Quorum size: 2 of 3 (tolerates 1 node failure)

### Moving Target Defense (MTD)

Services rotate ports dynamically every 5 minutes:
- **Product Service**: 8001-8011
- **Payment Service**: 8012-8022
- **API Gateway**: 8080-8090

Client applications must query Service Registry for current ports.

### Security Stack

**Vault Integration:**
- Secrets engine: KV v2 at `/secret`
- Service authentication tokens
- BFT node credentials
- All services connect to Vault at startup

**Wazuh Monitoring:**
- Real-time threat detection
- Log aggregation and analysis
- Active response capabilities
- Dashboard at https://localhost:443

## Common Tasks

### View Service Logs

```bash
# Specific service
docker-compose logs -f vault
docker-compose logs -f order-node-1

# All services
docker-compose logs -f
```

### Access Vault Secrets

```bash
# Read a service token
curl -H "X-Vault-Token: $(cat .vault/root-token)" \
  http://localhost:8200/v1/secret/data/services/product-service | jq .

# List BFT node secrets
curl -H "X-Vault-Token: $(cat .vault/root-token)" \
  http://localhost:8200/v1/secret/metadata/bft-cluster/ | jq .
```

### Restart a Service

```bash
# Restart single service
docker-compose restart order-node-1

# Restart all
docker-compose restart
```

### Stop and Clean Up

```bash
# Stop all containers
docker-compose stop

# Remove containers and volumes (deletes data)
docker-compose down -v

# Or use the cleanup script
./scripts/cleanup.sh
```

## Troubleshooting

### Port 8200 Already in Use

**Problem:** `Error starting vault: bind: address already in use`

**Solution:**
```bash
# Check what's using port 8200
lsof -i :8200

# Kill the process
kill -9 <PID>

# Or use Docker cleanup
docker-compose down -v
docker-compose up -d vault
sleep 60
./scripts/init-vault.sh
```

### Vault Service Not Ready

**Problem:** `curl: (7) Failed to connect to localhost port 8200`

**Solution:**
```bash
# Wait longer for Vault to initialize
sleep 120

# Check container logs
docker-compose logs vault

# Verify Vault is running
docker-compose ps vault
```

### Services Can't Connect to Vault

**Problem:** Services fail with Vault connection errors

**Solution:**
```bash
# Ensure Vault is initialized
./scripts/init-vault.sh

# Verify Vault is unsealed
curl http://localhost:8200/v1/sys/seal-status | jq .

# Export app token to services
export VAULT_TOKEN=$(cat .vault/app-token)
export VAULT_ADDR=http://localhost:8200
```

### Container Memory Issues

**Problem:** Services crash with OOM or CPU issues

**Solution:**
```bash
# Reduce Wazuh memory
# Edit docker-compose.yml:
# OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m

# Check resource usage
docker stats

# Restart with reduced services
docker-compose up -d registry vault api-gateway web-service
```

## File Structure

```
├── docker-compose.yml          # Main orchestration file
├── .vault/                     # Vault credentials (generated, git-ignored)
│   ├── root-token
│   ├── unseal-key
│   └── app-token
├── vault/
│   ├── Dockerfile              # Custom Vault image
│   ├── config.hcl              # Vault server config
│   └── policies/               # ACL policies
├── services/
│   ├── registry/               # Service registry (MTD coordinator)
│   ├── order-service/          # BFT cluster service
│   ├── product-service/        # Product service (MTD)
│   ├── payment-service/        # Payment service (MTD)
│   ├── email-service/          # Email service
│   ├── api-gateway/            # API gateway with load balancing
│   └── web-service/            # Frontend service
├── wazuh/
│   ├── config/                 # Wazuh configuration
│   ├── custom_rules.xml        # Custom detection rules
│   └── config/custom_decoder.xml
├── monitoring/
│   ├── prometheus/
│   │   ├── prometheus.yml      # Prometheus config
│   │   └── alerts.yml          # Alert rules
│   ├── grafana/
│   │   └── dashboards/         # Grafana dashboards
│   └── alertmanager/
│       └── config.yml          # Alertmanager config
└── scripts/
    ├── init-vault.sh           # Vault initialization
    ├── setup.sh                # Project setup
    ├── cleanup.sh              # Full cleanup
    ├── check-vault.sh          # Vault health check
    ├── test-bft.sh             # BFT testing
    └── vault-init.sh           # Legacy initialization
```

## Next Steps

1. **Customize Services**: Update Dockerfiles in `services/` to match your business logic
2. **Configure Monitoring**: Add Grafana dashboards in `monitoring/grafana/dashboards/`
3. **Setup Alerts**: Configure notification receivers in `monitoring/alertmanager/config.yml`
4. **Security Hardening**: Review and update Wazuh rules in `wazuh/custom_rules.xml`
5. **Deploy**: Use provided manifests for Kubernetes deployment (see deployment guides)

## Support

For issues or questions:
1. Check logs: `docker-compose logs [service]`
2. Consult IMPLEMENTATION_GUIDE.md for architecture details
3. Review VAULT_INTEGRATION.md for secret management setup
4. See TESTING_GUIDE.md for testing procedures

## License

See LICENSE file for terms.
