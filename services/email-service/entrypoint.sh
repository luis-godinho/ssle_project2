#!/bin/bash
set -e

echo "--- Configuring Wazuh Agent ---"

echo "--- Starting Services ---"

useradd spamd -s /bin/false
useradd -m -s /bin/bash luis

# Start rsyslog in foreground mode
echo "Starting rsyslog..."
rm -f /run/rsyslogd.pid
rsyslogd -n &
sleep 1

# Configure Postfix hostname
postconf -e "myhostname = mail-server.local"
postconf -e "mydestination = mail-server.local, localhost.localdomain, localhost"

# Start Postfix & Dovecot
echo "Starting Postfix..."
/etc/init.d/postfix start

echo "Starting Dovecot..."
/etc/init.d/dovecot start

# Start SpamAssassin
echo "Starting SpamAssassin..."
if [ -f /etc/init.d/spamassassin ]; then
    sed -i 's/ENABLED=0/ENABLED=1/' /etc/default/spamassassin
    /etc/init.d/spamassassin start
else
    spamd -d
fi

# Start Wazuh Agent
echo "Starting Wazuh Agent..."
/var/ossec/bin/wazuh-control start

echo "--- Mail Server Deployed Successfully ---"
echo "Wazuh Manager IP: $MANAGER_IP"

# Ensure mail.log exists before tail
touch /var/log/mail.log
echo "127.0.0.1 mail-server" >>/etc/hosts

echo "Registering with service registry..."
python3 /register.py &

echo "--- Tailing mail logs ---"
tail -F /var/log/mail.log
