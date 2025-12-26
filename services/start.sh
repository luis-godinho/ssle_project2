#!/bin/bash

# Start Wazuh agent
/var/ossec/bin/wazuh-control start

# Wait for Wazuh to initialize
sleep 5

# Start application
python3 app.py