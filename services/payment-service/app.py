#!/usr/bin/env python3
"""
Payment Service - Payment processing

Features:
- Payment processing (simulated)
- Transaction history
- Prometheus metrics
- Wazuh logging
"""

import json
import logging
import os
import random
import time
import uuid
from threading import Lock

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/var/log/payment-service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://registry:5000")

# In-memory payment database
payments = {}
payment_lock = Lock()

# Prometheus metrics
payment_requests = Counter(
    "payment_service_requests_total",
    "Total requests to payment service",
    ["method", "endpoint", "status"]
)
payment_total = Counter(
    "payment_transactions_total",
    "Total number of payment transactions",
    ["status"]
)
payment_amount = Counter(
    "payment_total_amount",
    "Total payment amount processed"
)
request_duration = Histogram(
    "payment_service_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint"]
)


@app.before_request
def start_timer():
    request.start_time = time.time()


@app.after_request
def record_metrics(response):
    if hasattr(request, 'start_time'):
        duration = time.time() - request.start_time
        endpoint = request.endpoint or 'unknown'
        
        payment_requests.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code
        ).inc()
        
        request_duration.labels(
            method=request.method,
            endpoint=endpoint
        ).observe(duration)
    
    return response


def validate_card(card_number, cvv):
    """Basic card validation"""
    if not card_number or len(card_number) < 13:
        return False, "Invalid card number length"
    
    if not cvv or len(cvv) != 3:
        return False, "Invalid CVV"
    
    # Simulate validation (95% success rate)
    if random.random() < 0.95:
        return True, "Card valid"
    else:
        return False, "Card validation failed"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "service": "payment-service",
        "timestamp": time.time()
    }), 200


@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}


@app.route("/api/payments", methods=["POST"])
def process_payment():
    """Process a payment transaction"""
    data = request.get_json()
    
    required_fields = ['order_id', 'amount', 'payment_method']
    if not all(field in data for field in required_fields):
        logger.warning("Payment failed - missing required fields")
        return jsonify({"error": "Missing required fields"}), 400
    
    order_id = data['order_id']
    amount = float(data['amount'])
    payment_method = data['payment_method']
    card_number = data.get('card_number', '')
    cvv = data.get('cvv', '')
    
    # Validate card
    if payment_method == 'credit_card':
        valid, message = validate_card(card_number, cvv)
        if not valid:
            logger.warning(f"Payment failed for order {order_id}: {message}")
            payment_total.labels(status="failed").inc()
            return jsonify({"error": message}), 400
    
    # Process payment (simulated)
    payment_id = str(uuid.uuid4())
    
    # Simulate payment gateway delay
    time.sleep(random.uniform(0.1, 0.5))
    
    # 98% success rate for valid payments
    success = random.random() < 0.98
    
    with payment_lock:
        payments[payment_id] = {
            "id": payment_id,
            "order_id": order_id,
            "amount": amount,
            "payment_method": payment_method,
            "status": "completed" if success else "failed",
            "timestamp": time.time(),
            "card_last4": card_number[-4:] if card_number else "N/A"
        }
    
    if success:
        payment_total.labels(status="success").inc()
        payment_amount.inc(amount)
        logger.info(f"Payment successful: {payment_id} - Order {order_id} - ${amount:.2f}")
        return jsonify(payments[payment_id]), 200
    else:
        payment_total.labels(status="failed").inc()
        logger.warning(f"Payment failed: Order {order_id} - Gateway error")
        return jsonify({
            "error": "Payment processing failed",
            "message": "Please try again or use a different payment method"
        }), 402


@app.route("/api/payments/<payment_id>", methods=["GET"])
def get_payment(payment_id):
    """Get payment details"""
    with payment_lock:
        payment = payments.get(payment_id)
    
    if not payment:
        return jsonify({"error": "Payment not found"}), 404
    
    return jsonify(payment), 200


@app.route("/api/payments", methods=["GET"])
def list_payments():
    """List all payments"""
    order_id = request.args.get('order_id')
    
    with payment_lock:
        if order_id:
            filtered = [p for p in payments.values() if p['order_id'] == order_id]
            result = filtered
        else:
            result = list(payments.values())
    
    return jsonify({"payments": result, "count": len(result)}), 200


@app.route("/api/payments/<payment_id>/refund", methods=["POST"])
def refund_payment(payment_id):
    """Refund a payment"""
    with payment_lock:
        if payment_id not in payments:
            return jsonify({"error": "Payment not found"}), 404
        
        payment = payments[payment_id]
        
        if payment['status'] != 'completed':
            return jsonify({"error": "Cannot refund payment"}), 400
        
        payment['status'] = 'refunded'
        payment['refunded_at'] = time.time()
    
    logger.info(f"Payment refunded: {payment_id} - ${payment['amount']:.2f}")
    return jsonify(payment), 200


if __name__ == "__main__":
    from register import register_service
    from threading import Thread
    
    registration_thread = Thread(target=register_service, daemon=True)
    registration_thread.start()
    
    logger.info("Payment Service starting on port 8003...")
    app.run(host="0.0.0.0", port=8003, debug=False)