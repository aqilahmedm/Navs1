#!/bin/sh
# Starts the portal over HTTPS (creates a self-signed certificate on first run).  Open https://127.0.0.1:5000
[ -f certs/cert.pem ] || sh make_cert.sh "$1" || exit 1
APAAR_HTTPS=1 python app.py
