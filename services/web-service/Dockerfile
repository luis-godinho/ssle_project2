FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Apache, mod_wsgi, Python, and dependencies
RUN apt-get update && apt-get install -y \
    apache2 \
    libapache2-mod-wsgi-py3 \
    python3 \
    python3-pip \
    curl \
    gnupg \
    iptables \
    && rm -rf /var/lib/apt/lists/*

# Install Flask and requests
RUN pip3 install flask requests

# Install Wazuh agent
RUN curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | gpg --no-default-keyring --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg --import \
    && chmod 644 /usr/share/keyrings/wazuh.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" | tee -a /etc/apt/sources.list.d/wazuh.list \
    && apt-get update \
    && apt-get install -y wazuh-agent \
    && rm -rf /var/lib/apt/lists/*

# Copy Apache configuration (preserves Shellshock test scripts)
COPY config/apache2.conf /etc/apache2/apache2.conf
COPY config/000-default.conf /etc/apache2/sites-available/000-default.conf

# Copy Wazuh agent config
COPY config/ossec.conf /var/ossec/etc/ossec.conf

# Copy Flask app
COPY app.py /app/app.py
COPY flaskapp.wsgi /app/flaskapp.wsgi
WORKDIR /app

# Configure Apache site for Flask and vulnerable CGI
RUN echo "WSGIScriptAlias / /app/flaskapp.wsgi" > /etc/apache2/sites-available/flaskapp.conf \
    && echo "<Directory /app>\n    <Files flaskapp.wsgi>\n        Require all granted\n    </Files>\n</Directory>" >> /etc/apache2/sites-available/flaskapp.conf \
    && ln -s /etc/apache2/sites-available/flaskapp.conf /etc/apache2/sites-enabled/flaskapp.conf

# Preserve existing CGI support for Shellshock
RUN a2enmod wsgi cgi

# Create vulnerable CGI script for testing
RUN mkdir -p /usr/lib/cgi-bin && \
    echo '#!/bin/bash' > /usr/lib/cgi-bin/test.sh && \
    echo 'echo "Content-type: text/html"' >> /usr/lib/cgi-bin/test.sh && \
    echo 'echo ""' >> /usr/lib/cgi-bin/test.sh && \
    echo 'echo "<html><body>Test CGI Script</body></html>"' >> /usr/lib/cgi-bin/test.sh && \
    chmod +x /usr/lib/cgi-bin/test.sh


EXPOSE 80


RUN pip install requests
COPY ./scripts/register.py /register.py

COPY scripts/start.sh /usr/local/bin/start.sh
RUN chmod +x /usr/local/bin/start.sh

CMD ["/usr/local/bin/start.sh"]
