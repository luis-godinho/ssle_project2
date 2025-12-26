#!/usr/bin/env python3
"""
Service Registry with Moving Target Defense (MTD) and Load Balancing

Features:
- Service registration and discovery
- Dynamic port allocation for MTD
- Health monitoring
- Port rotation management
- Service location tracking
- Load balancing for BFT clusters (round-robin)
- Deadlock-free rotation (lock released before response)
"""

import json
import logging
import random
import time
from datetime import datetime, timedelta
from threading import Lock, Thread

import requests
from flask import Flask, jsonify, request
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Port ranges for MTD rotation
PORT_RANGES = {
    "product-service": (8001, 8011),
    "payment-service": (8012, 8022),
    "email-service": (2525, 2534),
    "api-gateway": (8080, 8090),
}

# Service registry
services = {}  # {service_name: {url, port, host, health, last_heartbeat, rotation_count}}
services_lock = Lock()

# Load balancer state (for round-robin)
load_balancer_index = {}  # {service_name: current_index}
load_balancer_lock = Lock()

# Prometheus metrics
registry_services_total = Gauge("registry_services_total", "Total registered services")
registry_rotations_total = Counter(
    "registry_rotations_total", "Total port rotations", ["service"]
)
registry_heartbeats_total = Counter(
    "registry_heartbeats_total", "Total heartbeats received"
)
registry_loadbalance_requests = Counter(
    "registry_loadbalance_requests_total", "Total load-balanced requests", ["service"]
)


def allocate_port(service_name, exclude_ports=None):
    """Allocate a new port for a service from its range (NO LOCK - caller must hold lock)"""
    if service_name not in PORT_RANGES:
        return None

    min_port, max_port = PORT_RANGES[service_name]
    exclude = exclude_ports or []

    # Get currently used ports for this service
    used_ports = [
        s["port"] for s in services.values() if s.get("service_name") == service_name
    ]

    exclude.extend(used_ports)

    # Available ports
    available = [p for p in range(min_port, max_port + 1) if p not in exclude]

    if not available:
        logger.error(f"No available ports for {service_name}")
        return None

    # Random selection for unpredictability
    return random.choice(available)


@app.route("/register", methods=["POST"])
def register():
    """Register a service with the registry"""
    data = request.get_json()

    if not data or "name" not in data or "port" not in data:
        return jsonify({"error": "Missing name or port"}), 400

    service_name = data["name"]
    port = data["port"]
    host = data.get("host", service_name)
    metadata = data.get("metadata", {})

    with services_lock:
        services[service_name] = {
            "service_name": service_name,
            "url": f"http://{host}:{port}",
            "port": port,
            "host": host,
            "healthy": True,
            "last_heartbeat": time.time(),
            "rotation_count": services.get(service_name, {}).get("rotation_count", 0),
            "registered_at": datetime.now().isoformat(),
            "metadata": metadata,
        }
        registry_services_total.set(len(services))

    logger.info(f"Registered service: {service_name} at {host}:{port}")
    if metadata.get("type") == "bft-cluster-member":
        logger.info(
            f"  BFT cluster member: {metadata.get('node_id')} (role: {metadata.get('node_role')})"
        )

    return jsonify({"status": "registered", "service": service_name, "port": port}), 200


@app.route("/discover/<service_name>", methods=["GET"])
def discover(service_name):
    """Discover current location of a service with load balancing for BFT clusters"""
    with services_lock:
        # Check if this is a BFT cluster (multiple nodes registered)
        cluster_members = [
            name
            for name in services.keys()
            if name.startswith(f"{service_name}-")
            and services[name].get("metadata", {}).get("type") == "bft-cluster-member"
        ]

        if cluster_members:
            # BFT cluster detected - do load balancing
            healthy_members = [
                name for name in cluster_members if services[name]["healthy"]
            ]

            if not healthy_members:
                return jsonify(
                    {"error": f"No healthy nodes in {service_name} cluster"}
                ), 503

            # Round-robin load balancing
            with load_balancer_lock:
                if service_name not in load_balancer_index:
                    load_balancer_index[service_name] = 0

                index = load_balancer_index[service_name] % len(healthy_members)
                selected_node = healthy_members[index]
                load_balancer_index[service_name] = (index + 1) % len(healthy_members)

            service = services[selected_node]
            registry_loadbalance_requests.labels(service=service_name).inc()

            logger.debug(f"Load-balanced {service_name} -> {selected_node}")

            return jsonify(
                {
                    "name": service_name,
                    "url": service["url"],
                    "port": service["port"],
                    "host": service["host"],
                    "load_balanced": True,
                    "selected_node": selected_node,
                    "healthy_nodes": len(healthy_members),
                    "total_nodes": len(cluster_members),
                }
            ), 200

        # Single service (not a cluster)
        if service_name not in services:
            return jsonify({"error": f"Service {service_name} not found"}), 404

        service = services[service_name]

        if not service["healthy"]:
            return jsonify({"error": f"Service {service_name} is unhealthy"}), 503

        return jsonify(
            {
                "name": service_name,
                "url": service["url"],
                "port": service["port"],
                "host": service["host"],
                "load_balanced": False,
            }
        ), 200


@app.route("/services", methods=["GET"])
def list_services():
    """List all registered services"""
    with services_lock:
        return jsonify(
            {
                "services": [
                    {
                        "name": name,
                        "url": info["url"],
                        "port": info["port"],
                        "healthy": info["healthy"],
                        "rotation_count": info["rotation_count"],
                        "last_heartbeat": info["last_heartbeat"],
                        "metadata": info.get("metadata", {}),
                    }
                    for name, info in services.items()
                ]
            }
        ), 200


@app.route("/services/status", methods=["GET"])
def services_status():
    """Detailed service status"""
    current_time = time.time()
    with services_lock:
        return jsonify(
            {
                "services": [
                    {
                        "name": name,
                        "url": info["url"],
                        "port": info["port"],
                        "healthy": info["healthy"],
                        "rotation_count": info["rotation_count"],
                        "seconds_since_heartbeat": int(
                            current_time - info["last_heartbeat"]
                        ),
                        "registered_at": info["registered_at"],
                        "metadata": info.get("metadata", {}),
                    }
                    for name, info in services.items()
                ],
                "total_services": len(services),
            }
        ), 200


@app.route("/rotate/<service_name>", methods=["POST"])
def rotate(service_name):
    """
    Trigger port rotation for a service.
    Now actively triggers the service to rotate via its /rotate endpoint.
    """
    # Allocate new port and update state INSIDE lock
    with services_lock:
        if service_name not in services:
            return jsonify({"error": f"Service {service_name} not found"}), 404

        # Get current port
        current_port = services[service_name]["port"]

        # Allocate new port (allocate_port assumes lock is held)
        new_port = allocate_port(service_name, exclude_ports=[current_port])

        if not new_port:
            return jsonify({"error": "No available ports for rotation"}), 500

        # Increment rotation count
        services[service_name]["rotation_count"] += 1
        rotation_count = services[service_name]["rotation_count"]

        # Get service URL
        service_url = services[service_name]["url"]

        # Log inside lock
        logger.info(
            f"Rotation requested for {service_name}: {current_port} -> {new_port}"
        )

        # Prepare response data
        response_data = {
            "service": service_name,
            "old_port": current_port,
            "new_port": new_port,
            "rotation_time": datetime.now().isoformat(),
            "rotation_count": rotation_count,
        }

        # Update metrics
        registry_rotations_total.labels(service=service_name).inc()

    # LOCK IS NOW RELEASED!

    # Try to trigger rotation on the service itself
    request_data = request.get_json(silent=True) or {}
    skip_callback = request_data.get("skip_callback", False)

    if not skip_callback:
        # Try to trigger rotation on the service
        try:
            service_rotate_url = f"{service_url}/rotate"
            rotate_response = requests.post(
                service_rotate_url,
                json={"new_port": new_port},
                timeout=10,
            )

            if rotate_response.status_code == 200:
                logger.info(f"✅ Service {service_name} rotated to port {new_port}")
                response_data["service_rotated"] = True
            else:
                logger.warning(
                    f"⚠️ Service rotation failed: {rotate_response.status_code}"
                )
                response_data["service_rotated"] = False

        except Exception as e:
            logger.error(f"❌ Failed to trigger service rotation: {e}")
            response_data["service_rotated"] = False

    return jsonify(response_data), 200


@app.route("/heartbeat/<service_name>", methods=["POST"])
def heartbeat(service_name):
    """Receive heartbeat from a service"""
    with services_lock:
        if service_name not in services:
            return jsonify({"error": "Service not registered"}), 404

        services[service_name]["last_heartbeat"] = time.time()
        services[service_name]["healthy"] = True
        registry_heartbeats_total.inc()

    return jsonify({"status": "heartbeat received"}), 200


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy",
            "services_count": len(services),
            "timestamp": time.time(),
        }
    ), 200


@app.route("/metrics")
def metrics():
    """Prometheus metrics"""
    from flask import Response

    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


def health_checker():
    """Background thread to check service health"""
    HEALTH_TIMEOUT = 60  # seconds (increased for BFT nodes)

    while True:
        time.sleep(10)
        current_time = time.time()

        with services_lock:
            for name, info in services.items():
                if current_time - info["last_heartbeat"] > HEALTH_TIMEOUT:
                    if info["healthy"]:
                        logger.warning(
                            f"Service {name} marked unhealthy (no heartbeat for {HEALTH_TIMEOUT}s)"
                        )
                        info["healthy"] = False


if __name__ == "__main__":
    logger.info("Service Registry starting...")
    logger.info(f"Port ranges configured: {PORT_RANGES}")
    logger.info("Load balancing enabled for BFT clusters")
    logger.info("Deadlock-free rotation enabled")

    # Start health checker thread
    health_thread = Thread(target=health_checker, daemon=True)
    health_thread.start()

    app.run(host="0.0.0.0", port=5000, debug=False)
