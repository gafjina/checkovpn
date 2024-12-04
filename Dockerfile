FROM python:3.10-slim
WORKDIR /app

RUN apt-get update && \
    apt-get install -y \
    openvpn \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 5000

# Jalankan aplikasi Flask menggunakan Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
