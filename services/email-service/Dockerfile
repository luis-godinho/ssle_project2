FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl gnupg apt-transport-https rsyslog procps vim net-tools python3 python3-pip \
    postfix dovecot-imapd mailutils spamassassin spamc

# Install Wazuh Agent
RUN curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | gpg --no-default-keyring --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg --import && \
    chmod 644 /usr/share/keyrings/wazuh.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" | tee -a /etc/apt/sources.list.d/wazuh.list && \
    apt-get update && \
    WAZUH_MANAGER="wazuh.manager" apt-get install -y wazuh-agent && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /var/spool/rsyslog

# Replace rsyslog with Docker-safe config
COPY ./config/rsyslog-docker.conf /etc/rsyslog.conf

# Postfix configs
COPY ./config/main.cf /etc/postfix/main.cf
COPY ./config/master.cf /etc/postfix/master.cf
COPY ./config/header_checks /etc/postfix/header_checks

# SpamAssassin rules
COPY ./local.cf /etc/spamassassin/local.cf

# Ensure directories exist
RUN mkdir -p /var/mail && chmod 777 /var/mail

# Configure Wazuh to read mail.log
RUN sed -i '/<ossec_config>/a \
  <localfile>\n\
    <log_format>syslog</log_format>\n\
    <location>/var/log/mail.log</location>\n\
  </localfile>' /var/ossec/etc/ossec.conf

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN pip install requests --break-system-packages
COPY ./scripts/register.py /register.py

EXPOSE 25 143
ENTRYPOINT ["/entrypoint.sh"]
