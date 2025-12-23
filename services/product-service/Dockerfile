FROM python:3.11-slim

WORKDIR /app

# Install iptables for MTD port hopping
RUN apt-get update && \
    apt-get install -y --no-install-recommends iptables && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8000-8011

CMD ["python", "app.py"]
