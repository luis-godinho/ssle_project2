#!/usr/bin/env python3
"""
Service registration script
Registers the web service with the service registry
"""

import os
import sys
import time
import requests
import logging
from threading import Thread

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REGISTRY_URL = os.environ.get('REGISTRY_URL', 'http://registry:5000')
SERVICE_NAME = os.environ.get('SERVICE_NAME', 'web-service')
SERVICE_PORT = os.environ.get('SERVICE_PORT', '80')
HEARTBEAT_INTERVAL = 30  # seconds

def get_container_ip():
    """Get the container's IP address"""
    import socket
    try:
        # Get hostname
        hostname = socket.gethostname()
        # Get IP address
        ip = socket.gethostbyname(hostname)
        return ip
    except Exception as e:
        logger.error(f"Failed to get container IP: {e}")
        return 'web-service'  # Fallback to container name

def register_service():
    """Register this service with the registry"""
    max_retries = 10
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            ip = get_container_ip()
            service_url = f"http://{SERVICE_NAME}:{SERVICE_PORT}"
            
            payload = {
                'name': SERVICE_NAME,
                'url': service_url,
                'health_endpoint': '/index.html',
                'metadata': {
                    'type': 'web',
                    'monitored': True,
                    'wazuh_agent': True,
                    'ip': ip
                }
            }
            
            response = requests.post(
                f"{REGISTRY_URL}/register",
                json=payload,
                timeout=5
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Successfully registered {SERVICE_NAME} at {service_url}")
                return True
            else:
                logger.warning(f"Registration attempt {attempt + 1} failed: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Registration attempt {attempt + 1} failed: {e}")
        
        if attempt < max_retries - 1:
            logger.info(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
    
    logger.error(f"Failed to register after {max_retries} attempts")
    return False

def send_heartbeat():
    """Send periodic heartbeat to registry"""
    while True:
        try:
            response = requests.post(
                f"{REGISTRY_URL}/heartbeat/{SERVICE_NAME}",
                timeout=5
            )
            if response.status_code == 200:
                logger.debug(f"Heartbeat sent successfully")
            else:
                logger.warning(f"Heartbeat failed: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
        
        time.sleep(HEARTBEAT_INTERVAL)

if __name__ == '__main__':
    # Register service
    if register_service():
        # Start heartbeat thread
        heartbeat_thread = Thread(target=send_heartbeat, daemon=True)
        heartbeat_thread.start()
        logger.info("Service registration complete, heartbeat thread started")
    else:
        logger.error("Service registration failed")
        sys.exit(1)
