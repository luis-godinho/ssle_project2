#!/usr/bin/env python3
"""
Product Service with Moving Target Defense (MTD)

Features:
- Product catalog management
- REAL MTD port rotation capability (not just registration)
- Service registry integration
- Prometheus metrics
- Dynamic port switching
"""

import json
import logging
import os
import signal
import sys
import time
from threading import Thread, Event
from multiprocessing import Process, Value

from flask import Flask, jsonify, request
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from werkzeug.serving import make_server

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
current_port = Value('i', INITIAL_PORT)  # Shared between processes
server_process = None
shutdown_event = Event()

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
        "port": current_port.value,
        "mtd_enabled": MTD_ENABLED,
        "timestamp": time.time(),
    }), 200


@app.route("/metrics")
def metrics():
    """Prometheus metrics"""
    from flask import Response
    # Update stock metrics
    for prod_id, prod in products.items():
        product_stock_gauge.labels(product_id=prod_id).set(prod["stock"])
    mtd_current_port.set(current_port.value)
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route("/api/products", methods=["GET"])
def list_products():
    """List all products"""
    product_requests_total.inc()
    return jsonify({
        "products": list(products.values()),
        "count": len(products),
        "service_port": current_port.value,
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
    while not shutdown_event.is_set():
        try:
            requests.post(
                f"{REGISTRY_URL}/heartbeat/{SERVICE_NAME}",
                json={"port": current_port.value},
                timeout=5,
            )
            logger.debug(f"Heartbeat sent (port {current_port.value})")
        except Exception as e:
            logger.debug(f"Heartbeat error: {e}")
        
        time.sleep(30)


def run_flask_server(port):
    """Run Flask server on specified port"""
    logger.info(f"🚀 Starting Flask server on port {port}")
    
    try:
        server = make_server('0.0.0.0', port, app, threaded=True)
        server.serve_forever()
    except Exception as e:
        logger.error(f"Server error on port {port}: {e}")


def mtd_rotation_loop():
    """Automatic MTD rotation loop - polls registry for rotation signal"""
    global server_process
    
    while not shutdown_event.is_set():
        try:
            time.sleep(ROTATION_INTERVAL)
            
            if shutdown_event.is_set():
                break
            
            logger.info(f"🔄 Requesting port rotation from registry...")
            
            # Ask registry for new port
            response = requests.post(
                f"{REGISTRY_URL}/rotate/{SERVICE_NAME}",
                timeout=10,
            )
            
            if response.status_code == 200:
                data = response.json()
                new_port = data.get("new_port")
                old_port = current_port.value
                
                if new_port and new_port != old_port:
                    logger.info(f"🔄 MTD: Rotating from port {old_port} to {new_port}")
                    
                    # Start new server on new port
                    new_process = Process(target=run_flask_server, args=(new_port,))
                    new_process.start()
                    time.sleep(2)  # Give new server time to start
                    
                    # Register new port
                    if register_with_registry(new_port):
                        # Update current port
                        current_port.value = new_port
                        mtd_rotations_total.inc()
                        
                        # Terminate old server
                        if server_process and server_process.is_alive():
                            logger.info(f"🛑 Shutting down old server on port {old_port}")
                            server_process.terminate()
                            server_process.join(timeout=5)
                        
                        server_process = new_process
                        logger.info(f"✅ MTD rotation complete: {old_port} → {new_port}")
                    else:
                        logger.error("Failed to register new port, keeping old port")
                        new_process.terminate()
            else:
                logger.warning(f"Rotation request failed: {response.status_code}")
                
        except Exception as e:
            logger.error(f"MTD rotation error: {e}")
            time.sleep(10)


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Shutdown signal received")
    shutdown_event.set()
    
    global server_process
    if server_process and server_process.is_alive():
        server_process.terminate()
    
    sys.exit(0)


if __name__ == "__main__":
    logger.info(f"Product Service starting...")
    logger.info(f"Initial port: {INITIAL_PORT}")
    logger.info(f"MTD enabled: {MTD_ENABLED}")
    logger.info(f"Rotation interval: {ROTATION_INTERVAL}s")
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Set initial port
    current_port.value = INITIAL_PORT
    
    # Start initial server process
    server_process = Process(target=run_flask_server, args=(INITIAL_PORT,))
    server_process.start()
    time.sleep(3)
    
    if MTD_ENABLED:
        # Register with service registry
        register_with_registry(INITIAL_PORT)
        
        # Start heartbeat thread
        heartbeat_thread = Thread(target=send_heartbeat, daemon=True)
        heartbeat_thread.start()
        
        # Start MTD rotation loop
        logger.info(f"🔄 MTD rotation enabled (interval: {ROTATION_INTERVAL}s)")
        rotation_thread = Thread(target=mtd_rotation_loop, daemon=True)
        rotation_thread.start()
    
    # Keep main process alive
    try:
        while not shutdown_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        shutdown_event.set()
        if server_process:
            server_process.terminate()
