#!/usr/bin/env python3
"""
Product Service with Moving Target Defense (MTD) using iptables

Features:
- Product catalog management
- REAL MTD port rotation via iptables NAT rules
- Service runs on fixed internal port, external port hops via iptables
- Service registry integration
- Prometheus metrics
"""

import json
import logging
import os
import subprocess
import time
from threading import Thread
from threading import Thread, Lock

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
INTERNAL_PORT = 8000  # Fixed internal port (never changes)
INITIAL_PORT = int(os.environ.get("INITIAL_PORT", "8001"))  # Initial external port
REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://registry:5000")
MTD_ENABLED = os.environ.get("MTD_ENABLED", "true").lower() == "true"
ROTATION_INTERVAL = int(os.environ.get("ROTATION_INTERVAL", "300"))  # 5 minutes

# Global state
current_external_port = INITIAL_PORT
rotation_count = 0
rotation_lock = Lock()

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
mtd_rotations_total = Counter("mtd_rotations_total", "Total MTD port rotations")
mtd_current_port = Gauge("mtd_current_port", "Current external port")


def setup_initial_iptables():
    """
    Setup initial iptables NAT rule to forward external port to internal port.
    This allows the service to run on INTERNAL_PORT while appearing on INITIAL_PORT.
    """
    try:
        # Remove any existing rules for this service first
        subprocess.run(
            [
                "iptables",
                "-t",
                "nat",
                "-D",
                "PREROUTING",
                "-p",
                "tcp",
                "--dport",
                str(current_external_port),
                "-j",
                "REDIRECT",
                "--to-port",
                str(INTERNAL_PORT),
            ],
            stderr=subprocess.DEVNULL,
        )

        # Add new rule: external_port -> INTERNAL_PORT
        result = subprocess.run(
            [
                "iptables",
                "-t",
                "nat",
                "-A",
                "PREROUTING",
                "-p",
                "tcp",
                "--dport",
                str(current_external_port),
                "-j",
                "REDIRECT",
                "--to-port",
                str(INTERNAL_PORT),
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            logger.info(
                f"✅ iptables: External port {current_external_port} -> Internal port {INTERNAL_PORT}"
            )
            return True
        else:
            logger.error(f"❌ iptables setup failed: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"❌ iptables error: {e}")
        return False


def rotate_iptables_port(old_port, new_port):
    """
    Rotate to new external port using iptables.
    1. Remove old rule (old_port -> INTERNAL_PORT)
    2. Add new rule (new_port -> INTERNAL_PORT)
    """
    try:
        # Remove old rule
        subprocess.run(
            [
                "iptables",
                "-t",
                "nat",
                "-D",
                "PREROUTING",
                "-p",
                "tcp",
                "--dport",
                str(old_port),
                "-j",
                "REDIRECT",
                "--to-port",
                str(INTERNAL_PORT),
            ],
            stderr=subprocess.DEVNULL,
        )

        logger.info(f"🛑 Removed iptables rule: {old_port} -> {INTERNAL_PORT}")

        # Add new rule
        result = subprocess.run(
            [
                "iptables",
                "-t",
                "nat",
                "-A",
                "PREROUTING",
                "-p",
                "tcp",
                "--dport",
                str(new_port),
                "-j",
                "REDIRECT",
                "--to-port",
                str(INTERNAL_PORT),
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            logger.info(f"✅ Added iptables rule: {new_port} -> {INTERNAL_PORT}")
            logger.info(f"🔄 MTD: External port rotated from {old_port} to {new_port}")
            return True
        else:
            logger.error(f"❌ iptables rotation failed: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"❌ iptables rotation error: {e}")
        return False


@app.route("/rotate", methods=["POST"])
def handle_rotation():
    """
    Handle MTD rotation request from external trigger.
    This endpoint allows manual rotation testing.
    """
    global current_external_port, rotation_count

    with rotation_lock:
        try:
            # Request new port from registry
            response = requests.post(
                f"{REGISTRY_URL}/rotate/{SERVICE_NAME}",
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                new_port = data.get("new_port")
                old_port = current_external_port

                if new_port and new_port != old_port:
                    # Rotate using iptables
                    if rotate_iptables_port(old_port, new_port):
                        current_external_port = new_port
                        rotation_count += 1
                        mtd_rotations_total.inc()

                        # Re-register with new port
                        register_with_registry(new_port)

                        logger.info(f"✅ Manual MTD rotation: {old_port} → {new_port}")

                        return jsonify(
                            {
                                "status": "success",
                                "old_port": old_port,
                                "new_port": new_port,
                                "rotation_count": rotation_count,
                            }
                        ), 200
                    else:
                        return jsonify({"error": "iptables rotation failed"}), 500
                else:
                    return jsonify({"error": "No port change needed"}), 400
            else:
                return jsonify(
                    {
                        "error": "Registry rotation failed",
                        "status": response.status_code,
                    }
                ), 500

        except Exception as e:
            logger.error(f"Rotation error: {e}")
            return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    return jsonify(
        {
            "status": "healthy",
            "service": SERVICE_NAME,
            "internal_port": INTERNAL_PORT,
            "external_port": current_external_port,
            "mtd_enabled": MTD_ENABLED,
            "rotation_count": rotation_count,
            "timestamp": time.time(),
        }
    ), 200


@app.route("/metrics")
def metrics():
    """Prometheus metrics"""
    from flask import Response

    for prod_id, prod in products.items():
        product_stock_gauge.labels(product_id=prod_id).set(prod["stock"])
    mtd_current_port.set(current_external_port)
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route("/api/products", methods=["GET"])
def list_products():
    """List all products"""
    product_requests_total.inc()
    return jsonify(
        {
            "products": list(products.values()),
            "count": len(products),
            "internal_port": INTERNAL_PORT,
            "external_port": current_external_port,
        }
    ), 200


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
                json={"name": SERVICE_NAME, "host": SERVICE_NAME, "port": port},
                timeout=5,
            )
            if response.status_code in [200, 201]:
                logger.info(f"✅ Registered with registry at port {port}")
                return True
        except Exception as e:
            logger.error(f"Registration error: {e}")
        if retry < max_retries - 1:
            time.sleep(2)
    return False


def send_heartbeat():
    """Send periodic heartbeat to registry"""
    while True:
        try:
            requests.post(
                f"{REGISTRY_URL}/heartbeat/{SERVICE_NAME}",
                json={"port": current_external_port},
                timeout=5,
            )
            logger.debug(f"Heartbeat sent (external port {current_external_port})")
        except Exception as e:
            logger.debug(f"Heartbeat error: {e}")
        time.sleep(30)


def mtd_rotation_loop():
    """Automatic MTD rotation loop using iptables"""
    global current_external_port, rotation_count

    while True:
        try:
            time.sleep(ROTATION_INTERVAL)

            logger.info(f"🔄 MTD: Requesting port rotation from registry...")

            # Ask registry for new port
            response = requests.post(
                f"{REGISTRY_URL}/rotate/{SERVICE_NAME}",
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                new_port = data.get("new_port")
                old_port = current_external_port

                if new_port and new_port != old_port:
                    # Rotate using iptables
                    if rotate_iptables_port(old_port, new_port):
                        current_external_port = new_port
                        rotation_count += 1
                        mtd_rotations_total.inc()

                        # Re-register with new port
                        register_with_registry(new_port)

                        logger.info(
                            f"✅ MTD rotation complete: {old_port} → {new_port}"
                        )
                    else:
                        logger.error("❌ MTD rotation failed")
        except Exception as e:
            logger.error(f"MTD rotation error: {e}")
            time.sleep(10)


if __name__ == "__main__":
    logger.info(f"Product Service with MTD starting...")
    logger.info(f"Internal port (fixed): {INTERNAL_PORT}")
    logger.info(f"External port (initial): {INITIAL_PORT}")
    logger.info(f"MTD enabled: {MTD_ENABLED}")
    logger.info(f"Rotation interval: {ROTATION_INTERVAL}s")

    if MTD_ENABLED:
        # Setup initial iptables rule
        if setup_initial_iptables():
            # Register with service registry
            register_with_registry(INITIAL_PORT)

            # Start heartbeat thread
            heartbeat_thread = Thread(target=send_heartbeat, daemon=True)
            heartbeat_thread.start()

            # Start MTD rotation loop
            logger.info(f"🔄 MTD: Automatic rotation enabled")
            rotation_thread = Thread(target=mtd_rotation_loop, daemon=True)
            rotation_thread.start()
        else:
            logger.warning(
                "⚠️  MTD disabled - iptables setup failed (need NET_ADMIN capability)"
            )

    # Start Flask on INTERNAL_PORT (iptables redirects external traffic here)
    app.run(host="0.0.0.0", port=INTERNAL_PORT, debug=False)
