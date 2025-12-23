#!/usr/bin/env python3
"""
Service registration for API Gateway
"""

import os
import time
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REGISTRY_URL = os.environ.get('REGISTRY_URL', 'http://registry:5000')
SERVICE_NAME = os.environ.get('SERVICE_NAME', 'api-gateway')
SERVICE_PORT = os.environ.get('SERVICE_PORT', '8080')
HEARTBEAT_INTERVAL = 30

def get_container_ip():
    import socket
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return ip
    except Exception as e:
        logger.error(f"Failed to get container IP: {e}")
        return 'api-gateway'

def register_service():
    max_retries = 10
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            ip = get_container_ip()
            
            payload = {
                'name': SERVICE_NAME,
                'port': int(SERVICE_PORT),
                'metadata': {
                    'type': 'gateway',
                    'protocol': 'http',
                    'rate_limiting': True,
                    'ddos_protection': True,
                    'ip': ip
                }
            }
            
            response = requests.post(
                f"{REGISTRY_URL}/register",
                json=payload,
                timeout=5
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Successfully registered {SERVICE_NAME} at port {SERVICE_PORT}")
                break
            else:
                logger.warning(f"⚠️  Registration attempt {attempt + 1} failed: {response.status_code}")
                if hasattr(response, 'text'):
                    logger.warning(f"Response: {response.text}")
        
        except Exception as e:
            logger.error(f"❌ Registration attempt {attempt + 1} failed: {e}")
        
        if attempt < max_retries - 1:
            logger.info(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
    
    # Send periodic heartbeats
    logger.info("💓 Starting heartbeat thread...")
    while True:
        try:
            response = requests.post(
                f"{REGISTRY_URL}/heartbeat/{SERVICE_NAME}",
                timeout=5
            )
            if response.status_code == 200:
                logger.debug(f"💓 Heartbeat sent successfully")
        except Exception as e:
            logger.warning(f"⚠️  Failed to send heartbeat: {e}")
        
        time.sleep(HEARTBEAT_INTERVAL)

if __name__ == "__main__":
    register_service()
