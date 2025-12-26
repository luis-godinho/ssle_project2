#!/bin/bash
set -e

echo "Starting API Gateway with Wazuh agent..."

# Wait for Wazuh manager to be ready
echo "Waiting for Wazuh manager..."
sleep 10

# Start Wazuh agent
echo "Starting Wazuh agent..."
/var/ossec/bin/wazuh-control start

# Start the API Gateway
echo "Starting API Gateway application..."
exec python app.py
