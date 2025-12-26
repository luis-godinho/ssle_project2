#!/usr/bin/env python3
import os
import time
import requests
import logging

logger = logging.getLogger(__name__)

REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://registry:5000")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "payment-service")
SERVICE_HOST = os.environ.get("SERVICE_HOST", "payment-service")
SERVICE_PORT = os.environ.get("SERVICE_PORT", "8003")
HEARTBEAT_INTERVAL = 30


def register_service():
    service_url = f"http://{SERVICE_HOST}:{SERVICE_PORT}"
    registered = False
    retry_count = 0
    max_retries = 10
    
    while not registered and retry_count < max_retries:
        try:
            response = requests.post(
                f"{REGISTRY_URL}/register",
                json={
                    "name": SERVICE_NAME,
                    "url": service_url,
                    "health_endpoint": "/health",
                    "metadata": {
                        "type": "backend-service",
                        "version": "1.0.0"
                    }
                },
                timeout=5
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Successfully registered {SERVICE_NAME} at {service_url}")
                registered = True
            else:
                retry_count += 1
                time.sleep(5)
        except Exception as e:
            logger.error(f"Error registering service: {e}")
            retry_count += 1
            time.sleep(5)
    
    while True:
        try:
            time.sleep(HEARTBEAT_INTERVAL)
            response = requests.post(
                f"{REGISTRY_URL}/heartbeat/{SERVICE_NAME}",
                timeout=5
            )
            if response.status_code != 200:
                logger.warning(f"Heartbeat failed: {response.status_code}")
        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")


if __name__ == "__main__":
    register_service()