#!/usr/bin/env python3
"""
API Gateway with DDoS detection (passive - logs to Wazuh)

Features:
- Rate limiting per IP address
- Request routing to backend services
- Service discovery via registry
- Request/response time monitoring
- Logs DoS attacks for Wazuh to block
"""

import json
import logging
import os
import time
from collections import defaultdict, deque
from threading import Lock, Thread

import requests
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from flask_limiter.util import get_remote_address
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

app = Flask(__name__)
CORS(app)

# Configure logging to file for Wazuh monitoring
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("/var/log/api-gateway.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Configuration
REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://registry:5000")

# DDoS detection
request_history = defaultdict(lambda: deque(maxlen=1000))
history_lock = Lock()

# Response time tracking for monitoring
response_times = deque(maxlen=100)

# Prometheus metrics
api_gateway_requests_total = Counter(
    "api_gateway_requests_total", "Total number of requests"
)
api_gateway_response_time = Gauge(
    "api_gateway_response_time_seconds", "Average response time in seconds"
)

# Thresholds for DDoS detection
DDOS_THRESHOLD_REQUESTS = 500  # requests per window
DDOS_THRESHOLD_WINDOW = 60  # seconds


def detect_ddos(ip_address):
    """Detect potential DDoS attack from IP"""
    current_time = time.time()

    with history_lock:
        # Add current request
        request_history[ip_address].append(current_time)

        # Count requests in window
        recent_requests = [
            t
            for t in request_history[ip_address]
            if current_time - t < DDOS_THRESHOLD_WINDOW
        ]

        if len(recent_requests) > DDOS_THRESHOLD_REQUESTS:
            # Log for Wazuh detection (no local block)
            logger.warning(
                f"WAZUH_DDOS_ALERT src_ip={ip_address} req_count={len(recent_requests)} window={DDOS_THRESHOLD_WINDOW}"
            )
            return True
        return False


@app.before_request
def ddos_log_only():
    """Just logs when an IP is behaving badly (no blocking - Wazuh handles that)"""
    api_gateway_requests_total.inc()
    ip = get_remote_address()
    detect_ddos(ip)


@app.after_request
def track_response_time(response):
    """Track response times for monitoring"""
    if hasattr(request, "start_time"):
        duration = time.time() - request.start_time
        response_times.append(duration)
        # Update average response time gauge
        if response_times:
            avg_time = sum(response_times) / len(response_times)
            api_gateway_response_time.set(avg_time)
    return response


@app.before_request
def start_timer():
    """Start timing the request"""
    request.start_time = time.time()


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy",
            "timestamp": time.time(),
            "total_requests": int(api_gateway_requests_total._value._value),
        }
    ), 200


@app.route("/metrics")
def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route(
    "/proxy/<service_name>/<path:path>", methods=["GET", "POST", "PUT", "DELETE"]
)
def proxy_request(service_name, path):
    """Proxy request to backend service"""

    try:
        # Discover service from registry
        response = requests.get(f"{REGISTRY_URL}/discover/{service_name}", timeout=5)

        if response.status_code != 200:
            return jsonify({"error": f"Service {service_name} not found"}), 404

        service_info = response.json()
        service_url = service_info["url"]

        # Forward request to service
        target_url = f"{service_url}/{path}"

        # Forward headers (excluding host)
        headers = {k: v for k, v in request.headers if k.lower() != "host"}

        # Make request to backend
        backend_response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            params=request.args,
            timeout=30,
        )

        # Return response
        return Response(
            backend_response.content,
            status=backend_response.status_code,
            headers=dict(backend_response.headers),
        )

    except requests.exceptions.Timeout:
        logger.error(f"Timeout calling {service_name}")
        return jsonify({"error": "Service timeout"}), 504

    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling {service_name}: {e}")
        return jsonify({"error": "Service unavailable"}), 503


@app.route("/", methods=["GET"])
def index():
    """Gateway information page"""
    return jsonify(
        {
            "service": "API Gateway",
            "version": "1.0.0",
            "endpoints": {
                "/health": "Health check",
                "/metrics": "Prometheus metrics",
                "/proxy/<service>/<path>": "Proxy to backend service",
            },
        }
    ), 200


if __name__ == "__main__":
    # Register with service registry
    from register import register_service

    registration_thread = Thread(target=register_service, daemon=True)
    registration_thread.start()

    logger.info("API Gateway starting...")
    logger.info(
        f"DDoS threshold: {DDOS_THRESHOLD_REQUESTS} requests per {DDOS_THRESHOLD_WINDOW} seconds"
    )

    app.run(host="0.0.0.0", port=8080, debug=False)
