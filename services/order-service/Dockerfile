FROM python:3.11-slim

WORKDIR /app

COPY . .
RUN pip install --no-cache-dir -r requirements.txt

# Copy vault client
# COPY vault_client.py .

# Copy service files
# COPY consensus.py .
# COPY app.py .

EXPOSE 8102 8112 8122

CMD ["python", "app.py"]
