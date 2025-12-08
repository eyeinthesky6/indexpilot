#!/bin/bash
# Generate self-signed SSL certificates for PostgreSQL (development use)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SSL_DIR="$PROJECT_ROOT/ssl"

echo "Generating self-signed SSL certificates for PostgreSQL..."
echo "============================================================"

# Create SSL directory
mkdir -p "$SSL_DIR"
cd "$SSL_DIR"

# Check if OpenSSL is available
if ! command -v openssl &> /dev/null; then
    echo "ERROR: OpenSSL is not installed."
    echo "Install OpenSSL:"
    echo "  - Linux: sudo apt-get install openssl"
    echo "  - Mac: brew install openssl"
    echo "  - Windows: Install from https://slproweb.com/products/Win32OpenSSL.html"
    exit 1
fi

# Generate private key (2048-bit RSA)
echo "1. Generating private key..."
openssl genrsa -out server.key 2048

# Generate certificate signing request
echo "2. Generating certificate signing request..."
# Use proper escaping for Windows paths in Git Bash
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    openssl req -new -key server.key -out server.csr \
        -subj "//C=US/ST=State/L=City/O=IndexPilot/CN=localhost"
else
    openssl req -new -key server.key -out server.csr \
        -subj "/C=US/ST=State/L=City/O=IndexPilot/CN=localhost"
fi

# Generate self-signed certificate (valid for 1 year)
echo "3. Generating self-signed certificate..."
openssl x509 -req -days 365 -in server.csr -signkey server.key -out server.crt

# Set proper permissions (Linux/Mac)
if [[ "$OSTYPE" != "msys" && "$OSTYPE" != "win32" ]]; then
    echo "4. Setting file permissions..."
    chmod 600 server.key
    chmod 644 server.crt
fi

# Clean up CSR
rm server.csr

echo ""
echo "============================================================"
echo "SSL certificates generated successfully!"
echo ""
echo "Files created:"
echo "  - $SSL_DIR/server.key (private key)"
echo "  - $SSL_DIR/server.crt (certificate)"
echo ""
echo "Next steps:"
echo "  1. Update docker-compose.yml to enable SSL"
echo "  2. Uncomment SSL configuration lines"
echo "  3. Restart PostgreSQL: docker-compose restart postgres"
echo ""
echo "WARNING: These are self-signed certificates for development only."
echo "Do NOT use in production!"

