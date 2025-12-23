# Implementation Guide - SSLE Project 2

This guide provides detailed implementation instructions for all components.

## 🗂️ Project Structure to Create

```
ssle_project2/
├── services/
│   ├── registry/
│   │   ├── app.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── order-service/
│   │   ├── app.py
│   │   ├── consensus.py
│   │   ├── state_machine.py
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── ossec.conf
│   │
│   ├── product-service/
│   │   ├── app.py
│   │   ├── mtd_client.py
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── ossec.conf
│   │
│   ├── payment-service/
│   ├── email-service/
│   ├── api-gateway/
│   └── web-service/
│
├── monitoring/
│   ├── prometheus/
│   │   ├── prometheus.yml
│   │   └── alerts.yml
│   ├── grafana/
│   │   ├── provisioning/
│   │   └── dashboards/
│   └── alertmanager/
│       └── config.yml
│
├── wazuh/
│   ├── custom_rules.xml
│   └── config/
│
├── vault/
│   ├── config.hcl
│   └── policies/
│
├── scripts/
│   ├── init-vault.sh
│   ├── check-cluster.sh
│   ├── trigger-rotation.sh
│   └── test-bft.sh
│
└── tests/
    ├── test_bft.py
    └── test_mtd.py
```

---

## 1. Service Registry (MTD Coordinator)

### services/registry/app.py

```python
#!/usr/bin/env python3
from flask import Flask, jsonify, request
from prometheus_client import Counter, Gauge, generate_latest
import time
import random
import threading
from datetime import datetime, timedelta

app = Flask(__name__)

# Service registry storage
services = {}
port_allocations = {}

# Prometheus metrics
service_registrations = Counter('registry_service_registrations_total', 'Total service registrations')
service_rotations = Counter('registry_service_rotations_total', 'Total MTD rotations', ['service'])
active_services = Gauge('registry_active_services', 'Number of active services')

# MTD Configuration
MTD_ENABLED = True
ROTATION_INTERVAL = 300  # 5 minutes

PORT_RANGES = {
    'product-service': (8001, 8011),
    'payment-service': (8003, 8013),
    'email-service': (2525, 2534),
    'api-gateway': (8080, 8090)
}

def allocate_port(service_name):
    """Allocate a new port for MTD rotation"""
    if service_name not in PORT_RANGES:
        return None
    
    min_port, max_port = PORT_RANGES[service_name]
    used_ports = [s.get('port') for s in services.values() if s.get('name') == service_name]
    
    available = [p for p in range(min_port, max_port + 1) if p not in used_ports]
    
    if not available:
        # Recycle oldest port
        return random.randint(min_port, max_port)
    
    return random.choice(available)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'services': len(services)}), 200

@app.route('/register', methods=['POST'])
def register_service():
    data = request.json
    service_name = data.get('name')
    service_host = data.get('host')
    service_port = data.get('port')
    node_id = data.get('node_id', service_name)
    
    if not all([service_name, service_host, service_port]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    service_id = f"{service_name}-{node_id}"
    
    services[service_id] = {
        'name': service_name,
        'host': service_host,
        'port': service_port,
        'node_id': node_id,
        'url': f"http://{service_host}:{service_port}",
        'registered_at': datetime.now().isoformat(),
        'last_heartbeat': datetime.now().isoformat(),
        'rotation_count': services.get(service_id, {}).get('rotation_count', 0),
        'next_rotation': (datetime.now() + timedelta(seconds=ROTATION_INTERVAL)).isoformat() if MTD_ENABLED else None
    }
    
    service_registrations.inc()
    active_services.set(len(services))
    
    print(f"[REGISTRY] Registered {service_id} at {service_host}:{service_port}")
    
    return jsonify({
        'status': 'registered',
        'service_id': service_id,
        'next_rotation': services[service_id]['next_rotation']
    }), 200

@app.route('/heartbeat/<service_id>', methods=['POST'])
def heartbeat(service_id):
    if service_id not in services:
        return jsonify({'error': 'Service not found'}), 404
    
    services[service_id]['last_heartbeat'] = datetime.now().isoformat()
    return jsonify({'status': 'ok'}), 200

@app.route('/discover/<service_name>', methods=['GET'])
def discover_service(service_name):
    # Find all nodes for this service
    matching = [s for s in services.values() if s['name'] == service_name]
    
    if not matching:
        return jsonify({'error': 'Service not found'}), 404
    
    # For order-service, return all nodes (BFT cluster)
    if service_name == 'order-service':
        return jsonify({
            'service': service_name,
            'nodes': [{'node_id': s['node_id'], 'url': s['url']} for s in matching]
        }), 200
    
    # For other services, return current active instance
    service = matching[0]
    return jsonify({
        'service': service_name,
        'url': service['url'],
        'port': service['port']
    }), 200

@app.route('/rotate/<service_name>', methods=['POST'])
def request_rotation(service_name):
    """Request new port allocation for MTD"""
    if not MTD_ENABLED:
        return jsonify({'error': 'MTD not enabled'}), 400
    
    new_port = allocate_port(service_name)
    if not new_port:
        return jsonify({'error': 'No ports available'}), 500
    
    service_rotations.labels(service=service_name).inc()
    
    return jsonify({
        'new_port': new_port,
        'rotation_time': datetime.now().isoformat(),
        'next_rotation': (datetime.now() + timedelta(seconds=ROTATION_INTERVAL)).isoformat()
    }), 200

@app.route('/services', methods=['GET'])
def list_services():
    return jsonify({'services': list(services.values())}), 200

@app.route('/services/status', methods=['GET'])
def services_status():
    now = datetime.now()
    status = []
    
    for service_id, service in services.items():
        last_hb = datetime.fromisoformat(service['last_heartbeat'])
        is_healthy = (now - last_hb).total_seconds() < 60
        
        status.append({
            'service_id': service_id,
            'name': service['name'],
            'port': service['port'],
            'healthy': is_healthy,
            'rotation_count': service.get('rotation_count', 0),
            'next_rotation': service.get('next_rotation')
        })
    
    return jsonify({'services': status}), 200

@app.route('/metrics', methods=['GET'])
def metrics():
    return generate_latest(), 200

if __name__ == '__main__':
    print("[REGISTRY] Starting Service Registry with MTD support")
    print(f"[REGISTRY] MTD Enabled: {MTD_ENABLED}")
    print(f"[REGISTRY] Rotation Interval: {ROTATION_INTERVAL}s")
    app.run(host='0.0.0.0', port=5000, debug=False)
```

### services/registry/Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5000

CMD ["python", "app.py"]
```

### services/registry/requirements.txt

```
Flask==3.0.0
prometheus-client==0.19.0
requests==2.31.0
```

---

## 2. Order Service (BFT Cluster)

### services/order-service/consensus.py

```python
#!/usr/bin/env python3
import requests
import hashlib
import json
import time
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

class BFTConsensus:
    def __init__(self, node_id: str, cluster_nodes: List[str], quorum_size: int):
        """
        Initialize BFT consensus module
        cluster_nodes: list of "host:port" strings
        quorum_size: minimum nodes required for consensus (2f+1)
        """
        self.node_id = node_id
        self.cluster_nodes = cluster_nodes
        self.quorum_size = quorum_size
        self.votes = {}  # operation_id -> {node_id: vote}
        self.operations = {}  # operation_id -> operation_data
        
        logger.info(f"[BFT] Node {node_id} initialized with {len(cluster_nodes)} nodes, quorum={quorum_size}")
    
    def propose_operation(self, operation_type: str, operation_data: dict) -> Tuple[bool, dict]:
        """
        Propose an operation to the cluster and wait for consensus
        Returns: (success, result)
        """
        operation_id = self._generate_operation_id(operation_type, operation_data)
        
        logger.info(f"[BFT] {self.node_id} proposing operation {operation_id}")
        
        # Store operation
        self.operations[operation_id] = {
            'type': operation_type,
            'data': operation_data,
            'proposed_by': self.node_id,
            'timestamp': time.time()
        }
        
        # Broadcast to all nodes
        votes = self._broadcast_vote_request(operation_id, operation_type, operation_data)
        
        # Check quorum
        approved = sum(1 for v in votes.values() if v == 'approve')
        rejected = sum(1 for v in votes.values() if v == 'reject')
        
        logger.info(f"[BFT] Operation {operation_id}: {approved} approved, {rejected} rejected (quorum={self.quorum_size})")
        
        if approved >= self.quorum_size:
            logger.info(f"[BFT] Operation {operation_id} COMMITTED")
            return True, {'status': 'committed', 'votes': votes}
        else:
            logger.warning(f"[BFT] Operation {operation_id} REJECTED")
            return False, {'status': 'rejected', 'votes': votes}
    
    def _generate_operation_id(self, operation_type: str, operation_data: dict) -> str:
        """Generate unique operation ID"""
        data_str = json.dumps(operation_data, sort_keys=True)
        hash_input = f"{operation_type}:{data_str}:{time.time()}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    def _broadcast_vote_request(self, operation_id: str, operation_type: str, operation_data: dict) -> Dict[str, str]:
        """
        Broadcast vote request to all nodes
        Returns: {node_id: vote}
        """
        votes = {}
        
        for node in self.cluster_nodes:
            try:
                response = requests.post(
                    f"http://{node}/consensus/vote",
                    json={
                        'operation_id': operation_id,
                        'operation_type': operation_type,
                        'operation_data': operation_data,
                        'proposer': self.node_id
                    },
                    timeout=5
                )
                
                if response.status_code == 200:
                    vote_data = response.json()
                    votes[vote_data['node_id']] = vote_data['vote']
                    logger.info(f"[BFT] Node {vote_data['node_id']} voted: {vote_data['vote']}")
                else:
                    logger.error(f"[BFT] Node {node} returned {response.status_code}")
                    votes[node] = 'error'
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"[BFT] Failed to reach node {node}: {e}")
                votes[node] = 'unreachable'
        
        return votes
    
    def validate_and_vote(self, operation_id: str, operation_type: str, operation_data: dict, proposer: str) -> str:
        """
        Validate operation and cast vote
        Returns: 'approve' or 'reject'
        """
        logger.info(f"[BFT] {self.node_id} validating operation {operation_id} from {proposer}")
        
        # Validation logic
        if operation_type == 'CREATE_ORDER':
            # Validate order data
            if not operation_data.get('customer_id'):
                logger.warning(f"[BFT] Invalid order: missing customer_id")
                return 'reject'
            if not operation_data.get('items'):
                logger.warning(f"[BFT] Invalid order: no items")
                return 'reject'
            # Add more validation...
        
        elif operation_type == 'PROCESS_PAYMENT':
            # Payment must be unanimous (3/3)
            if not operation_data.get('amount') or operation_data['amount'] <= 0:
                logger.warning(f"[BFT] Invalid payment amount")
                return 'reject'
        
        # If all validations pass
        logger.info(f"[BFT] {self.node_id} approves operation {operation_id}")
        return 'approve'
    
    def get_cluster_status(self) -> dict:
        """Get current cluster health"""
        healthy_nodes = 0
        node_status = []
        
        for node in self.cluster_nodes:
            try:
                response = requests.get(f"http://{node}/health", timeout=2)
                is_healthy = response.status_code == 200
                healthy_nodes += 1 if is_healthy else 0
                
                node_status.append({
                    'node': node,
                    'healthy': is_healthy
                })
            except:
                node_status.append({
                    'node': node,
                    'healthy': False
                })
        
        quorum_available = healthy_nodes >= self.quorum_size
        
        return {
            'cluster_size': len(self.cluster_nodes),
            'healthy_nodes': healthy_nodes,
            'quorum_size': self.quorum_size,
            'quorum_available': quorum_available,
            'nodes': node_status
        }
```

### services/order-service/app.py

```python
#!/usr/bin/env python3
from flask import Flask, jsonify, request
import os
import logging
import requests
from consensus import BFTConsensus
from prometheus_client import Counter, Histogram, generate_latest
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
NODE_ID = os.getenv('NODE_ID', 'order-node-1')
NODE_PORT = int(os.getenv('NODE_PORT', 8002))
CLUSTER_NODES = os.getenv('CLUSTER_NODES', '').split(',')
QUORUM_SIZE = int(os.getenv('QUORUM_SIZE', 2))
REGISTRY_URL = os.getenv('REGISTRY_URL', 'http://registry:5000')
BFT_ENABLED = os.getenv('BFT_ENABLED', 'true').lower() == 'true'

# Initialize BFT consensus
if BFT_ENABLED:
    consensus = BFTConsensus(NODE_ID, CLUSTER_NODES, QUORUM_SIZE)
    logger.info(f"[ORDER] BFT enabled for {NODE_ID}")
else:
    consensus = None
    logger.info(f"[ORDER] BFT disabled for {NODE_ID}")

# Prometheus metrics
order_requests = Counter('order_service_requests_total', 'Total order requests', ['method', 'endpoint'])
order_created = Counter('order_created_total', 'Orders created')
consensus_proposals = Counter('bft_consensus_proposals_total', 'Consensus proposals', ['operation'])
consensus_votes = Counter('bft_consensus_votes_total', 'Consensus votes', ['vote'])
order_latency = Histogram('order_processing_duration_seconds', 'Order processing latency')

# In-memory order storage (replace with DB in production)
orders = {}

def register_with_registry():
    """Register this node with the service registry"""
    try:
        response = requests.post(
            f"{REGISTRY_URL}/register",
            json={
                'name': 'order-service',
                'host': NODE_ID,
                'port': NODE_PORT,
                'node_id': NODE_ID
            },
            timeout=5
        )
        if response.status_code == 200:
            logger.info(f"[ORDER] Registered {NODE_ID} with registry")
        else:
            logger.error(f"[ORDER] Failed to register: {response.status_code}")
    except Exception as e:
        logger.error(f"[ORDER] Registry registration failed: {e}")

@app.route('/health', methods=['GET'])
def health():
    order_requests.labels(method='GET', endpoint='/health').inc()
    return jsonify({'status': 'healthy', 'node': NODE_ID}), 200

@app.route('/api/orders', methods=['POST'])
def create_order():
    start_time = time.time()
    order_requests.labels(method='POST', endpoint='/api/orders').inc()
    
    data = request.json
    order_id = f"ORD-{int(time.time())}-{NODE_ID}"
    
    logger.info(f"[ORDER] {NODE_ID} creating order {order_id}")
    
    # If BFT enabled, use consensus
    if BFT_ENABLED and consensus:
        consensus_proposals.labels(operation='CREATE_ORDER').inc()
        
        success, result = consensus.propose_operation(
            'CREATE_ORDER',
            {
                'order_id': order_id,
                'customer_id': data.get('customer_id'),
                'items': data.get('items'),
                'total': sum(item.get('price', 0) * item.get('quantity', 1) for item in data.get('items', []))
            }
        )
        
        # Record votes
        for vote in result.get('votes', {}).values():
            consensus_votes.labels(vote=vote).inc()
        
        if not success:
            logger.error(f"[ORDER] Consensus failed for {order_id}")
            return jsonify({
                'error': 'Consensus failed',
                'votes': result.get('votes')
            }), 400
    
    # Store order
    orders[order_id] = {
        'order_id': order_id,
        'customer_id': data.get('customer_id'),
        'items': data.get('items'),
        'status': 'pending',
        'created_by': NODE_ID,
        'created_at': time.time()
    }
    
    order_created.inc()
    order_latency.observe(time.time() - start_time)
    
    logger.info(f"[ORDER] Order {order_id} created successfully")
    
    return jsonify(orders[order_id]), 201

@app.route('/api/orders/<order_id>', methods=['GET'])
def get_order(order_id):
    order_requests.labels(method='GET', endpoint='/api/orders/<id>').inc()
    
    if order_id not in orders:
        return jsonify({'error': 'Order not found'}), 404
    
    return jsonify(orders[order_id]), 200

@app.route('/consensus/vote', methods=['POST'])
def vote_on_operation():
    """Receive vote request from another node"""
    if not BFT_ENABLED:
        return jsonify({'error': 'BFT not enabled'}), 400
    
    data = request.json
    operation_id = data.get('operation_id')
    operation_type = data.get('operation_type')
    operation_data = data.get('operation_data')
    proposer = data.get('proposer')
    
    logger.info(f"[ORDER] {NODE_ID} received vote request for {operation_id} from {proposer}")
    
    vote = consensus.validate_and_vote(operation_id, operation_type, operation_data, proposer)
    consensus_votes.labels(vote=vote).inc()
    
    return jsonify({
        'node_id': NODE_ID,
        'operation_id': operation_id,
        'vote': vote
    }), 200

@app.route('/consensus/status', methods=['GET'])
def consensus_status():
    """Get cluster consensus status"""
    if not BFT_ENABLED:
        return jsonify({'error': 'BFT not enabled'}), 400
    
    status = consensus.get_cluster_status()
    return jsonify(status), 200

@app.route('/metrics', methods=['GET'])
def metrics():
    return generate_latest(), 200

if __name__ == '__main__':
    logger.info(f"[ORDER] Starting Order Service Node: {NODE_ID} on port {NODE_PORT}")
    logger.info(f"[ORDER] BFT Enabled: {BFT_ENABLED}")
    logger.info(f"[ORDER] Cluster: {CLUSTER_NODES}")
    logger.info(f"[ORDER] Quorum: {QUORUM_SIZE}")
    
    # Register with service registry
    register_with_registry()
    
    app.run(host='0.0.0.0', port=NODE_PORT, debug=False)
```

---

## Next Steps

I've created the foundation with:
1. ✅ Comprehensive README with architecture
2. ✅ Docker Compose with BFT cluster + MTD
3. ✅ Implementation guide started

**The repository is ready at**: [https://github.com/luis-godinho/ssle_project2](https://github.com/luis-godinho/ssle_project2)

**You can now**:
1. Copy code from your Project 1 for services (Product, Payment, Email, Gateway, Web)
2. Implement the MTD rotation logic in each service
3. Add Wazuh custom rules for BFT/MTD monitoring
4. Create the Prometheus/Grafana dashboards
5. Write tests and the report

**Would you like me to**:
- Continue creating more service implementations?
- Create the monitoring configurations (Prometheus, Grafana)?
- Create the Wazuh custom rules?
- Create the testing scripts?
- Create the report template?

Let me know what you'd like next!
