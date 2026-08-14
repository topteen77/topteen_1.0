#!/usr/bin/env bash
# Generate self-signed SSL certificate for TopTeens.
# Production domain: topteen.in (use Let's Encrypt for real certs).
# Dev: demo.topteen.in or 43.204.127.118 – HTTP is enough; this script is for quick HTTPS on IP/dev.
# Usage: ./generate-ssl.sh [domain_or_ip]
# Example: ./generate-ssl.sh topteen.in
# Example: ./generate-ssl.sh 43.204.127.118

set -e

SSL_DIR="${SSL_CERT_PATH:-./ssl}"
mkdir -p "$SSL_DIR"

# Default: production domain; or pass demo.topteen.in / 43.204.127.118 for dev
IP_OR_DOMAIN="${1:-topteen.in}"

echo "Generating self-signed SSL certificate for: $IP_OR_DOMAIN"
echo "Certificate will be saved to: $SSL_DIR"

openssl genrsa -out "$SSL_DIR/key.pem" 2048

if [[ "$IP_OR_DOMAIN" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  SAN="IP:$IP_OR_DOMAIN,DNS:$IP_OR_DOMAIN"
else
  SAN="DNS:$IP_OR_DOMAIN,DNS:*.$IP_OR_DOMAIN,DNS:www.$IP_OR_DOMAIN"
fi

openssl req -new -x509 -key "$SSL_DIR/key.pem" -out "$SSL_DIR/cert.pem" -days 365 \
  -subj "/C=IN/ST=State/L=City/O=TopTeen/CN=$IP_OR_DOMAIN" \
  -addext "subjectAltName=$SAN"

chmod 600 "$SSL_DIR/key.pem"
chmod 644 "$SSL_DIR/cert.pem"

echo ""
echo "SSL certificate generated."
echo "  - $SSL_DIR/cert.pem"
echo "  - $SSL_DIR/key.pem"
echo ""
echo "Production (topteen.in): prefer Let's Encrypt. For dev/demo, self-signed is OK."
echo "Set SSL_CERT_PATH in .env if not using ./ssl, then: ./docker_files/deploy.sh up"
