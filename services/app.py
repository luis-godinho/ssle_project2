#!/usr/bin/env python3
"""
Product Service - E-commerce product catalog

Features:
- Product CRUD operations
- Inventory management
- Product search and filtering
- Registry discovery for inter-service communication
- Prometheus metrics
- Wazuh logging for security monitoring
"""

import json
import logging
import os
import time
from threading import Lock

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

app = Flask(__name__)
CORS(app)

# Configure logging for Wazuh
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/var/log/product-service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://registry:5000")

# In-memory product database (in production, this would be a real database)
products = {
    "PROD001": {
        "id": "PROD001",
        "name": "Laptop",
        "description": "High-performance laptop",
        "price": 999.99,
        "stock": 50,
        "category": "Electronics"
    },
    "PROD002": {
        "id": "PROD002",
        "name": "Wireless Mouse",
        "description": "Ergonomic wireless mouse",
        "price": 29.99,
        "stock": 200,
        "category": "Accessories"
    },
    "PROD003": {
        "id": "PROD003",
        "name": "USB-C Hub",
        "description": "7-in-1 USB-C hub",
        "price": 49.99,
        "stock": 150,
        "category": "Accessories"
    }
}
product_lock = Lock()

# Prometheus metrics
product_requests = Counter(
    "product_service_requests_total", 
    "Total requests to product service",
    ["method", "endpoint", "status"]
)
product_inventory = Gauge(
    "product_inventory_stock",
    "Current stock level for products",
    ["product_id", "product_name"]
)
request_duration = Histogram(
    "product_service_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint"]
)


@app.before_request
def start_timer():
    """Start timing the request"""
    request.start_time = time.time()


@app.after_request
def record_metrics(response):
    """Record Prometheus metrics after request"""
    if hasattr(request, 'start_time'):
        duration = time.time() - request.start_time
        endpoint = request.endpoint or 'unknown'
        
        product_requests.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code
        ).inc()
        
        request_duration.labels(
            method=request.method,
            endpoint=endpoint
        ).observe(duration)
    
    return response


def discover_service(service_name):
    """Discover a service URL from the registry"""
    try:
        response = requests.get(f"{REGISTRY_URL}/discover/{service_name}", timeout=5)
        if response.status_code == 200:
            service_info = response.json()
            return service_info.get('url')
        else:
            logger.error(f"Failed to discover {service_name}: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error discovering {service_name}: {e}")
        return None


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "product-service",
        "timestamp": time.time()
    }), 200


@app.route("/metrics")
def metrics():
    """Prometheus metrics endpoint"""
    # Update inventory gauges
    with product_lock:
        for product_id, product in products.items():
            product_inventory.labels(
                product_id=product_id,
                product_name=product['name']
            ).set(product['stock'])
    
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}


@app.route("/api/products", methods=["GET"])
def get_products():
    """Get all products or filter by category"""
    category = request.args.get('category')
    
    with product_lock:
        if category:
            filtered = {k: v for k, v in products.items() if v.get('category') == category}
            result = list(filtered.values())
        else:
            result = list(products.values())
    
    logger.info(f"GET /api/products - returned {len(result)} products")
    return jsonify({"products": result, "count": len(result)}), 200


@app.route("/api/products/<product_id>", methods=["GET"])
def get_product(product_id):
    """Get a specific product by ID"""
    with product_lock:
        product = products.get(product_id)
    
    if not product:
        logger.warning(f"Product not found: {product_id}")
        return jsonify({"error": "Product not found"}), 404
    
    logger.info(f"GET /api/products/{product_id} - success")
    return jsonify(product), 200


@app.route("/api/products", methods=["POST"])
def create_product():
    """Create a new product"""
    data = request.get_json()
    
    required_fields = ['id', 'name', 'price', 'stock']
    if not all(field in data for field in required_fields):
        logger.warning(f"Invalid product creation request - missing fields")
        return jsonify({"error": "Missing required fields"}), 400
    
    product_id = data['id']
    
    with product_lock:
        if product_id in products:
            logger.warning(f"Attempted to create duplicate product: {product_id}")
            return jsonify({"error": "Product already exists"}), 409
        
        products[product_id] = {
            "id": product_id,
            "name": data['name'],
            "description": data.get('description', ''),
            "price": float(data['price']),
            "stock": int(data['stock']),
            "category": data.get('category', 'Uncategorized')
        }
    
    logger.info(f"Created product: {product_id} - {data['name']}")
    return jsonify(products[product_id]), 201


@app.route("/api/products/<product_id>", methods=["PUT"])
def update_product(product_id):
    """Update an existing product"""
    data = request.get_json()
    
    with product_lock:
        if product_id not in products:
            logger.warning(f"Attempted to update non-existent product: {product_id}")
            return jsonify({"error": "Product not found"}), 404
        
        product = products[product_id]
        
        # Update fields
        if 'name' in data:
            product['name'] = data['name']
        if 'description' in data:
            product['description'] = data['description']
        if 'price' in data:
            product['price'] = float(data['price'])
        if 'stock' in data:
            product['stock'] = int(data['stock'])
        if 'category' in data:
            product['category'] = data['category']
    
    logger.info(f"Updated product: {product_id}")
    return jsonify(product), 200


@app.route("/api/products/<product_id>/stock", methods=["POST"])
def update_stock(product_id):
    """Update product stock (used by order service)"""
    data = request.get_json()
    
    if 'quantity' not in data:
        return jsonify({"error": "Missing quantity field"}), 400
    
    quantity_change = int(data['quantity'])
    
    with product_lock:
        if product_id not in products:
            logger.warning(f"Stock update failed - product not found: {product_id}")
            return jsonify({"error": "Product not found"}), 404
        
        product = products[product_id]
        new_stock = product['stock'] + quantity_change
        
        if new_stock < 0:
            logger.warning(f"Stock update failed - insufficient stock for {product_id}")
            return jsonify({"error": "Insufficient stock"}), 400
        
        product['stock'] = new_stock
        
        # Log significant stock changes for security monitoring
        if quantity_change < -10:
            logger.warning(f"Large stock decrease: {product_id} - {quantity_change} units")
    
    logger.info(f"Stock updated for {product_id}: {quantity_change:+d} (new stock: {product['stock']})")
    return jsonify({
        "product_id": product_id,
        "stock": product['stock'],
        "change": quantity_change
    }), 200


@app.route("/api/products/<product_id>", methods=["DELETE"])
def delete_product(product_id):
    """Delete a product"""
    with product_lock:
        if product_id not in products:
            logger.warning(f"Attempted to delete non-existent product: {product_id}")
            return jsonify({"error": "Product not found"}), 404
        
        deleted_product = products.pop(product_id)
    
    logger.warning(f"Product deleted: {product_id} - {deleted_product['name']}")
    return jsonify({"message": "Product deleted", "product": deleted_product}), 200


@app.route("/api/search", methods=["GET"])
def search_products():
    """Search products by name or description"""
    query = request.args.get('q', '').lower()
    
    if not query:
        return jsonify({"products": [], "count": 0}), 200
    
    with product_lock:
        results = [
            product for product in products.values()
            if query in product['name'].lower() or query in product.get('description', '').lower()
        ]
    
    logger.info(f"Search query '{query}' returned {len(results)} results")
    return jsonify({"products": results, "count": len(results), "query": query}), 200


if __name__ == "__main__":
    from register import register_service
    from threading import Thread
    
    # Register with service registry
    registration_thread = Thread(target=register_service, daemon=True)
    registration_thread.start()
    
    logger.info("Product Service starting on port 8001...")
    app.run(host="0.0.0.0", port=8001, debug=False)