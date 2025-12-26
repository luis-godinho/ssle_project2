#!/usr/bin/env python3
"""
Service registration script for email service
"""

import os
import sys
import time
import requests
import logging
from threading import Thread

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://registry:5000")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "email-service")
SERVICE_PORT = os.environ.get("SERVICE_PORT", "25")
HEARTBEAT_INTERVAL = 30  # seconds


def get_container_ip():
    """Get the container's IP address"""
    import socket

    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return ip
    except Exception as e:
        logger.error(f"Failed to get container IP: {e}")
        return "email-service"


def register_service():
    """Register this service with the registry"""
    max_retries = 10
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            ip = get_container_ip()
            service_url = f"http://{SERVICE_NAME}:{SERVICE_PORT}"

            payload = {
                "name": SERVICE_NAME,
                "url": service_url,
                "health_endpoint": "/",
                "metadata": {
                    "type": "email",
                    "monitored": True,
                    "wazuh_agent": True,
                    "spamassassin": True,
                    "ip": ip,
                    "smtp_port": 25,
                    "imap_port": 143,
                },
            }

            response = requests.post(
                f"{REGISTRY_URL}/register", json=payload, timeout=5
            )

            if response.status_code in [200, 201]:
                logger.info(f"Successfully registered {SERVICE_NAME}")
                return True
            else:
                logger.warning(
                    f"Registration attempt {attempt + 1} failed: {response.status_code}"
                )

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
                f"{REGISTRY_URL}/heartbeat/{SERVICE_NAME}", timeout=5
            )
            if response.status_code == 200:
                logger.info(f"sent to {REGISTRY_URL}/heartbeat/{SERVICE_NAME}")
                logger.debug(f"Heartbeat sent successfully")
            else:
                logger.warning(f"Heartbeat failed: {response.status_code}")
        except Exception as e:
            logger.info(f"Failed to send heartbeat: {e}")

        time.sleep(HEARTBEAT_INTERVAL)


if __name__ == "__main__":
    if register_service():
        logger.info("Starting heartbeat")
        send_heartbeat()
        logger.info("Service registration complete, heartbeat thread started")
    else:
        logger.error("Service registration failed")
        sys.exit(1)
