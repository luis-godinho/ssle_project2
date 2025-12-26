#!/usr/bin/env python3
"""
Product Service with Moving Target Defense (MTD) - Simplified Single-Process Version

Features:
- Product catalog management
- MTD port rotation (manual trigger via /rotate endpoint)
- Service registry integration
- Prometheus metrics
- Simple, reliable port switching
"""

import json
import logging
import os
import sys
import time
from threading import Thread

from flask import Flask, jsonify, request
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

import requests

app = Flask(__name__)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration
SERVICE_NAME = "product-service"
INITIAL_PORT = int(os.environ.get("INITIAL_PORT", "8001"))
REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://registry:5000")
MTD_ENABLED = os.environ.get("MTD_ENABLED", "true").lower() == "true"
ROTATION_INTERVAL = int(os.environ.get("ROTATION_INTERVAL", "300"))  # 5 minutes

# Global state
current_port = INITIAL_PORT
rotation_count = 0

# Sample products (in-memory - in production use shared DB)
products = {
    "PROD001": {"id": "PROD001", "name": "Laptop", "price": 999.99, "stock": 10},
    "PROD002": {"id": "PROD002", "name": "Mouse", "price": 29.99, "stock": 50},
    "PROD003": {"id": "PROD003", "name": "Keyboard", "price": 79.99, "stock": 30},
    "PROD004": {"id": "PROD004", "name": "Monitor", "price": 299.99, "stock": 15},
    "PROD005": {"id": "PROD005", "name": "Headphones", "price": 149.99, "stock": 25},
}

# Prometheus metrics
product_requests_total = Counter("product_requests_total", "Total product requests")
product_stock_gauge = Gauge("product_stock", "Product stock levels", ["product_id"])
mtd_rotations_total = Counter("mtd_rotations_total", "Total MTD port rotations")
mtd_current_port = Gauge("mtd_current_port", "Current service port")


@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "service": SERVICE_NAME,
        "port": current_port,
        "mtd_enabled": MTD_ENABLED,
        "rotation_count": rotation_count,
        "timestamp": time.time(),
    }), 200


@app.route("/metrics")
def metrics():
    """Prometheus metrics"""
    from flask import Response
    # Update stock metrics
    for prod_id, prod in products.items():
        product_stock_gauge.labels(product_id=prod_id).set(prod["stock"])
    mtd_current_port.set(current_port)
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route("/api/products", methods=["GET"])
def list_products():
    """List all products"""
    product_requests_total.inc()
    return jsonify({
        "products": list(products.values()),
        "count": len(products),
        "service_port": current_port,
    }), 200


@app.route("/api/products/<product_id>", methods=["GET"])
def get_product(product_id):
    """Get product by ID"""
    product_requests_total.inc()
    
    if product_id not in products:
        return jsonify({"error": "Product not found"}), 404
    
    return jsonify(products[product_id]), 200


@app.route("/api/products", methods=["POST"])
def create_product():
    """Create new product"""
    data = request.get_json()
    
    required = ["id", "name", "price"]
    if not all(field in data for field in required):
        return jsonify({"error": "Missing required fields"}), 400
    
    product_id = data["id"]
    if product_id in products:
        return jsonify({"error": "Product already exists"}), 400
    
    products[product_id] = {
        "id": product_id,
        "name": data["name"],
        "price": data["price"],
        "stock": data.get("stock", 0),
    }
    
    logger.info(f"Product created: {product_id}")
    return jsonify(products[product_id]), 201


@app.route("/api/products/<product_id>/stock", methods=["PUT"])
def update_stock(product_id):
    """Update product stock"""
    if product_id not in products:
        return jsonify({"error": "Product not found"}), 404
    
    data = request.get_json()
    if "stock" not in data:
        return jsonify({"error": "Missing stock field"}), 400
    
    products[product_id]["stock"] = data["stock"]
    logger.info(f"Stock updated for {product_id}: {data['stock']}")
    
    return jsonify(products[product_id]), 200


@app.route("/rotate", methods=["POST"])
def handle_rotation():
    """
    Handle MTD port rotation request.
    This triggers a container restart on a new port.
    
    NOTE: In true MTD, the container would be recreated by orchestrator (K8s, etc.)
    For this demo, service will restart itself via docker-compose.
    """
    global rotation_count, current_port
    
    try:
        # Request new port from registry
        response = requests.post(
            f"{REGISTRY_URL}/rotate/{SERVICE_NAME}",
            timeout=10,
        )
        
        if response.status_code == 200:
            data = response.json()
            new_port = data.get("new_port")
            old_port = current_port
            
            logger.info(f"🔄 MTD Rotation: {old_port} → {new_port}")
            logger.info(f"⚠️  Service needs restart to bind to new port {new_port}")
            logger.info(f"📦 Update INITIAL_PORT={new_port} and restart container")
            
            rotation_count += 1
            mtd_rotations_total.inc()
            
            # In production, orchestrator would recreate container on new port
            # For now, just update registry
            requests.post(
                f"{REGISTRY_URL}/register",
                json={
                    "name": SERVICE_NAME,
                    "host": SERVICE_NAME,
                    "port": new_port,
                },
                timeout=5,
            )
            
            return jsonify({
                "status": "rotation_acknowledged",
                "old_port": old_port,
                "new_port": new_port,
                "message": "Container restart required for port change",
                "action": f"docker-compose restart product-service with INITIAL_PORT={new_port}"
            }), 200
        else:
            return jsonify({"error": "Rotation failed", "status": response.status_code}), 500
            
    except Exception as e:
        logger.error(f"Rotation error: {e}")
        return jsonify({"error": str(e)}), 500


def register_with_registry(port):
    """Register service with registry at specific port"""
    max_retries = 5
    
    for retry in range(max_retries):
        try:
            response = requests.post(
                f"{REGISTRY_URL}/register",
                json={
                    "name": SERVICE_NAME,
                    "host": SERVICE_NAME,
                    "port": port,
                },
                timeout=5,
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Registered with registry at port {port}")
                return True
            else:
                logger.warning(f"Registration failed: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Error registering with registry: {e}")
        
        if retry < max_retries - 1:
            time.sleep(2)
    
    logger.error("Failed to register with registry")
    return False


def send_heartbeat():
    """Send periodic heartbeat to registry"""
    while True:
        try:
            requests.post(
                f"{REGISTRY_URL}/heartbeat/{SERVICE_NAME}",
                json={"port": current_port},
                timeout=5,
            )
            logger.debug(f"Heartbeat sent (port {current_port})")
        except Exception as e:
            logger.debug(f"Heartbeat error: {e}")
        
        time.sleep(30)


if __name__ == "__main__":
    logger.info(f"Product Service starting...")
    logger.info(f"Port: {INITIAL_PORT}")
    logger.info(f"MTD enabled: {MTD_ENABLED}")
    
    current_port = INITIAL_PORT
    
    if MTD_ENABLED:
        # Register with service registry
        register_with_registry(INITIAL_PORT)
        
        # Start heartbeat thread
        heartbeat_thread = Thread(target=send_heartbeat, daemon=True)
        heartbeat_thread.start()
        
        logger.info(f"🛡️  MTD: Service registered at port {INITIAL_PORT}")
        logger.info(f"🔄 MTD: Manual rotation via: POST /rotate or registry /rotate/{SERVICE_NAME}")
        logger.info(f"⚠️  MTD: True rotation requires container restart on new port")
    
    app.run(host="0.0.0.0", port=INITIAL_PORT, debug=False)
