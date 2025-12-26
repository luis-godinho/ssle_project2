#!/usr/bin/env python3
"""
Order Service with Byzantine Fault Tolerance (BFT) and Vault Authentication

Features:
- 3-node consensus cluster
- BFT consensus for order operations
- State replication
- Quorum-based decision making
- Vault-based node authentication
- Service registry integration for MTD
"""

import json
import logging
import os
import time
import requests
from datetime import datetime
from threading import Thread

from flask import Flask, jsonify, request
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

from consensus import BFTConsensus

app = Flask(__name__)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration
NODE_ID = os.environ.get("NODE_ID", "order-node-1")
NODE_PORT = int(os.environ.get("NODE_PORT", "8002"))
SERVICE_NAME = os.environ.get("SERVICE_NAME", "order-service")
REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://registry:5000")
CLUSTER_NODES = os.environ.get(
    "CLUSTER_NODES",
    "order-node-1:8002,order-node-2:8012,order-node-3:8022"
).split(",")

# Initialize BFT consensus
consensus = BFTConsensus(
    node_id=f"{NODE_ID}:{NODE_PORT}",
    cluster_nodes=CLUSTER_NODES
)

# In-memory order storage (in production, use distributed database)
orders = {}

# Prometheus metrics
order_created_total = Counter("order_created_total", "Total orders created")
order_consensus_proposals = Counter("order_consensus_proposals_total", "Total consensus proposals")
order_consensus_approved = Counter("order_consensus_approved_total", "Total approved operations")
order_consensus_rejected = Counter("order_consensus_rejected_total", "Total rejected operations")
order_cluster_quorum = Gauge("order_cluster_quorum_available", "Whether cluster has quorum")


def register_with_registry():
    """Register this node with the service registry (runs once at startup)"""
    max_retries = 10
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            # Only the primary node (node-1) registers as "order-service"
            # This provides a single entry point for the BFT cluster
            if NODE_ID == "order-node-1":
                logger.info(f"Registering {SERVICE_NAME} with registry at {REGISTRY_URL}")
                
                response = requests.post(
                    f"{REGISTRY_URL}/register",
                    json={
                        "service_name": SERVICE_NAME,
                        "port": NODE_PORT,
                        "hostname": NODE_ID,
                        "mtd_enabled": False,  # BFT cluster doesn't rotate ports
                        "metadata": {
                            "type": "bft-cluster",
                            "node_id": NODE_ID,
                            "cluster_size": len(CLUSTER_NODES),
                            "quorum_size": consensus.quorum_size
                        }
                    },
                    timeout=5
                )
                
                if response.status_code in [200, 201]:
                    logger.info(f"✅ Successfully registered {SERVICE_NAME} with registry")
                    return True
                else:
                    logger.warning(f"Registry returned status {response.status_code}: {response.text}")
            else:
                # Secondary nodes just log their status
                logger.info(f"Node {NODE_ID} is secondary - primary node handles registration")
                return True
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries} - Failed to register: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                logger.error("Failed to register with service registry after all retries")
                return False
    
    return False


def heartbeat_loop():
    """Send periodic heartbeats to service registry"""
    while True:
        try:
            time.sleep(30)  # Heartbeat every 30 seconds
            
            if NODE_ID == "order-node-1":  # Only primary sends heartbeats
                response = requests.post(
                    f"{REGISTRY_URL}/heartbeat",
                    json={
                        "service_name": SERVICE_NAME,
                        "port": NODE_PORT,
                        "healthy": True,
                        "metadata": {
                            "healthy_nodes": consensus.get_cluster_status()["healthy_nodes"],
                            "quorum_available": consensus.get_cluster_status()["quorum_available"]
                        }
                    },
                    timeout=5
                )
                
                if response.status_code != 200:
                    logger.warning(f"Heartbeat failed: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")


@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "node": NODE_ID,
        "port": NODE_PORT,
        "vault_auth": bool(consensus.auth_token),
        "timestamp": time.time(),
    }), 200


@app.route("/metrics")
def metrics():
    """Prometheus metrics"""
    from flask import Response
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route("/api/orders", methods=["POST"])
def create_order():
    """Create new order (requires consensus)"""
    data = request.get_json()
    
    if not data or "customer_id" not in data or "items" not in data:
        return jsonify({"error": "Missing required fields"}), 400
    
    logger.info(f"Order creation request from customer {data['customer_id']}")
    
    # Propose operation to cluster
    order_consensus_proposals.inc()
    result = consensus.propose_operation("CREATE_ORDER", data)
    
    if not result["success"]:
        order_consensus_rejected.inc()
        return jsonify({
            "error": "Order creation rejected by cluster",
            "reason": result.get("reason"),
            "votes": result["votes"],
        }), 400
    
    # Consensus achieved - create order
    order_consensus_approved.inc()
    order_created_total.inc()
    
    order_id = f"ORD-{int(time.time())}-{NODE_ID}"
    order = {
        "order_id": order_id,
        "customer_id": data["customer_id"],
        "items": data["items"],
        "status": "pending",
        "total": sum(item.get("price", 0) * item["quantity"] for item in data["items"]),
        "created_at": datetime.now().isoformat(),
        "created_by": NODE_ID,
        "consensus_operation_id": result["operation_id"],
        "authenticated_votes": result["approved"],
    }
    
    orders[order_id] = order
    
    logger.info(f"Order {order_id} created with consensus ({result['approved']}/{consensus.cluster_size} votes)")
    
    return jsonify(order), 201


@app.route("/api/orders/<order_id>", methods=["GET"])
def get_order(order_id):
    """Get order details"""
    if order_id not in orders:
        return jsonify({"error": "Order not found"}), 404
    
    return jsonify(orders[order_id]), 200


@app.route("/api/orders", methods=["GET"])
def list_orders():
    """List all orders"""
    return jsonify({
        "orders": list(orders.values()),
        "count": len(orders),
        "node": NODE_ID,
    }), 200


@app.route("/api/orders/<order_id>/status", methods=["PUT"])
def update_order_status(order_id):
    """Update order status (requires consensus)"""
    data = request.get_json()
    
    if not data or "status" not in data:
        return jsonify({"error": "Missing status field"}), 400
    
    if order_id not in orders:
        return jsonify({"error": "Order not found"}), 404
    
    # Propose status update
    order_consensus_proposals.inc()
    result = consensus.propose_operation("UPDATE_STATUS", {
        "order_id": order_id,
        "status": data["status"],
    })
    
    if not result["success"]:
        order_consensus_rejected.inc()
        return jsonify({
            "error": "Status update rejected by cluster",
            "votes": result["votes"],
        }), 400
    
    # Update status
    order_consensus_approved.inc()
    orders[order_id]["status"] = data["status"]
    orders[order_id]["updated_at"] = datetime.now().isoformat()
    orders[order_id]["updated_by"] = NODE_ID
    
    logger.info(f"Order {order_id} status updated to {data['status']} with consensus")
    
    return jsonify(orders[order_id]), 200


@app.route("/consensus/vote", methods=["POST"])
def vote_on_operation():
    """Vote on a proposed operation (with signature)"""
    data = request.get_json()
    
    required = ["operation_id", "operation_type", "operation_data", "proposer"]
    if not all(field in data for field in required):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Validate and vote (returns tuple: vote, signature)
    vote, signature = consensus.validate_and_vote(
        data["operation_id"],
        data["operation_type"],
        data["operation_data"],
        data["proposer"],
    )
    
    return jsonify({
        "node": f"{NODE_ID}:{NODE_PORT}",
        "vote": vote,
        "signature": signature,
        "operation_id": data["operation_id"],
    }), 200


@app.route("/consensus/status", methods=["GET"])
def consensus_status():
    """Get consensus cluster status"""
    status = consensus.get_cluster_status()
    order_cluster_quorum.set(1 if status["quorum_available"] else 0)
    return jsonify(status), 200


@app.route("/consensus/operations/<operation_id>", methods=["GET"])
def get_operation_status(operation_id):
    """Get status of a consensus operation"""
    op_status = consensus.get_operation_status(operation_id)
    
    if not op_status:
        return jsonify({"error": "Operation not found"}), 404
    
    return jsonify(op_status), 200


if __name__ == "__main__":
    logger.info(f"Order Service starting: {NODE_ID}")
    logger.info(f"Port: {NODE_PORT}")
    logger.info(f"Cluster nodes: {CLUSTER_NODES}")
    logger.info(f"Quorum requirement: {consensus.quorum_size}/{consensus.cluster_size}")
    logger.info(f"Vault authentication: {'enabled' if consensus.auth_token else 'disabled'}")
    
    # Register with service registry in background
    Thread(target=register_with_registry, daemon=True).start()
    
    # Start heartbeat thread (only for primary node)
    if NODE_ID == "order-node-1":
        Thread(target=heartbeat_loop, daemon=True).start()
    
    app.run(host="0.0.0.0", port=NODE_PORT, debug=False)
