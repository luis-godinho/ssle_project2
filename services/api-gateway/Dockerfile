FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and Wazuh agent
RUN apt-get update && \
    apt-get install -y curl gnupg apt-transport-https iptables && \
    curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | gpg --no-default-keyring --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg --import && \
    chmod 644 /usr/share/keyrings/wazuh.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" | tee -a /etc/apt/sources.list.d/wazuh.list && \
    apt-get update && \
    WAZUH_MANAGER="wazuh.manager" apt-get install -y wazuh-agent && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy Python requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY register.py .
COPY start.sh .

# Copy Wazuh agent configuration
COPY ossec.conf /var/ossec/etc/ossec.conf

# Make start script executable
RUN chmod +x start.sh

# Create log directory
RUN mkdir -p /var/log && touch /var/log/api-gateway.log

EXPOSE 8080

CMD ["./start.sh"]
