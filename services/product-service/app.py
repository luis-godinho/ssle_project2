#!/usr/bin/env python3
"""
Product Service with Moving Target Defense (MTD)

Features:
- Product catalog management
- MTD port rotation capability
- Service registry integration
- Prometheus metrics
"""

import json
import logging
import os
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
SERVICE_PORT = int(os.environ.get("SERVICE_PORT", "8001"))
REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://registry:5000")
MTD_ENABLED = os.environ.get("MTD_ENABLED", "true").lower() == "true"
MTD_ROTATION_INTERVAL = int(os.environ.get("MTD_ROTATION_INTERVAL", "300"))  # 5 minutes

# Sample products
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


@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "service": SERVICE_NAME,
        "port": SERVICE_PORT,
        "timestamp": time.time(),
    }), 200


@app.route("/metrics")
def metrics():
    """Prometheus metrics"""
    from flask import Response
    # Update stock metrics
    for prod_id, prod in products.items():
        product_stock_gauge.labels(product_id=prod_id).set(prod["stock"])
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route("/api/products", methods=["GET"])
def list_products():
    """List all products"""
    product_requests_total.inc()
    return jsonify({
        "products": list(products.values()),
        "count": len(products),
        "service_port": SERVICE_PORT,
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


def register_with_registry():
    """Register service with registry"""
    max_retries = 10
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            response = requests.post(
                f"{REGISTRY_URL}/register",
                json={
                    "name": SERVICE_NAME,
                    "host": SERVICE_NAME,
                    "port": SERVICE_PORT,
                },
                timeout=5,
            )
            
            if response.status_code == 200:
                logger.info(f"Registered with registry at port {SERVICE_PORT}")
                return True
            else:
                logger.warning(f"Registration failed: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Error registering with registry: {e}")
        
        retry_count += 1
        time.sleep(5)
    
    logger.error("Failed to register with registry after max retries")
    return False


def send_heartbeat():
    """Send periodic heartbeat to registry"""
    while True:
        try:
            requests.post(
                f"{REGISTRY_URL}/heartbeat/{SERVICE_NAME}",
                timeout=5,
            )
            logger.debug("Heartbeat sent to registry")
        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")
        
        time.sleep(10)


if __name__ == "__main__":
    logger.info(f"Product Service starting on port {SERVICE_PORT}")
    logger.info(f"MTD enabled: {MTD_ENABLED}")
    
    if MTD_ENABLED:
        # Register with service registry
        registration_thread = Thread(target=register_with_registry, daemon=True)
        registration_thread.start()
        
        # Start heartbeat thread
        heartbeat_thread = Thread(target=send_heartbeat, daemon=True)
        heartbeat_thread.start()
    
    app.run(host="0.0.0.0", port=SERVICE_PORT, debug=False)
