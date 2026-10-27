#!/bin/sh
# Self-signed certificate for local/LAN HTTPS. Your browser will warn once; for a real site use Caddy or Cloudflare (see README).
# Usage: sh make_cert.sh [your-LAN-IP]
mkdir -p certs
IP=${1:-127.0.0.1}
openssl req -x509 -newkey rsa:2048 -nodes -days 365 -keyout certs/key.pem -out certs/cert.pem \
  -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:$IP" && chmod 600 certs/key.pem && echo "Certificate created in ./certs"
