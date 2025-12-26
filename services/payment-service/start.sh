#!/bin/bash
/var/ossec/bin/wazuh-control start
sleep 5
python3 app.py