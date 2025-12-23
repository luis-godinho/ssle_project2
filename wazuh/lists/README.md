# Wazuh IP Reputation Lists

This directory contains IP reputation lists used by Wazuh for threat detection.

## blacklist-alienvault

This file contains IP addresses from the AlienVault reputation database plus any custom malicious IPs detected by the system.

### Setup

The file will be created automatically when the system detects threats. You can also pre-populate it:

```bash
# Download AlienVault reputation list
wget https://raw.githubusercontent.com/firehol/blocklist-ipsets/master/alienvault_reputation.ipset -O alienvault_reputation.ipset

# Convert to CDB format for Wazuh
wget https://wazuh.com/resources/iplist-to-cdblist.py -O iplist-to-cdblist.py
python3 iplist-to-cdblist.py alienvault_reputation.ipset blacklist-alienvault

# Set permissions
chown wazuh:wazuh blacklist-alienvault
```

### Adding Custom IPs

To manually add IPs to the blacklist:

```bash
# Add IP to source list
echo "192.168.1.100" >> alienvault_reputation.ipset

# Regenerate CDB file
python3 iplist-to-cdblist.py alienvault_reputation.ipset blacklist-alienvault

# Reload Wazuh
systemctl restart wazuh-manager
```

## Format

The file should be in CDB (Constant Database) format for efficient lookups. The conversion script handles this automatically.

## References

- [Wazuh IP Reputation Documentation](https://documentation.wazuh.com/current/user-manual/capabilities/threat-intelligence/index.html)
- [AlienVault IP Reputation](https://github.com/firehol/blocklist-ipsets)
