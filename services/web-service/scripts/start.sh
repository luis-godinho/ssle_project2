#!/bin/bash
set -e

echo "Starting Web Service..."

# Wait for Wazuh manager to be ready
echo "Waiting for Wazuh manager..."
sleep 10

# Start Wazuh agent
echo "Starting Wazuh agent..."
/var/ossec/bin/wazuh-control start

# Register with service registry
echo "Registering with service registry..."
python3 /register.py &

# Start Apache in foreground
echo "Starting Apache..."
source /etc/apache2/envvars
exec apachectl -DFOREGROUND
