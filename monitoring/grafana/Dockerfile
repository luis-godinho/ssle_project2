FROM grafana/grafana:latest

COPY provisioning /etc/grafana/provisioning

EXPOSE 3000

ENV GF_SECURITY_ADMIN_PASSWORD=admin
ENV GF_SECURITY_ADMIN_USER=admin
ENV GF_USERS_ALLOW_SIGN_UP=false
