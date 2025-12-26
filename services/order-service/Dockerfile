FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service files
COPY consensus.py .
COPY app.py .

EXPOSE 8002 8012 8022

CMD ["python", "app.py"]
