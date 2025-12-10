# SSL/TLS Configuration for PostgreSQL

**Date**: 08-12-2025  
**Status**: Guide for enabling SSL in PostgreSQL Docker container

---

## Overview

PostgreSQL supports SSL/TLS encryption for secure database connections. This guide explains how to enable SSL for the IndexPilot PostgreSQL container.

---

## SSL Options

### Option 1: Self-Signed Certificates (Development/Testing)

**Use case**: Local development, testing, internal networks

**Pros:**
- ✅ Free
- ✅ Easy to generate
- ✅ Good for development

**Cons:**
- ❌ Not trusted by browsers/clients (will show warnings)
- ❌ Not suitable for production

### Option 2: CA-Signed Certificates (Production)

**Use case**: Production deployments, external access

**Pros:**
- ✅ Trusted by all clients
- ✅ No warnings
- ✅ Production-ready

**Cons:**
- ❌ Requires certificate authority (CA)
- ❌ May cost money (commercial CA) or require setup (self-hosted CA)

### Option 3: Cloud Provider SSL (Recommended for Production)

**Use case**: Using cloud databases (AWS RDS, Google Cloud SQL, Azure Database)

**Pros:**
- ✅ Managed by cloud provider
- ✅ Automatically configured
- ✅ Production-ready

**Cons:**
- ❌ Requires cloud database (not local Docker)

---

## Option 1: Self-Signed Certificates (Development)

### Step 1: Generate Self-Signed Certificates

Create SSL certificates directory:

```bash
mkdir -p ssl
cd ssl
```

Generate server key and certificate:

```bash
# Generate private key
openssl genrsa -out server.key 2048

# Generate certificate signing request
openssl req -new -key server.key -out server.csr \
  -subj "/C=US/ST=State/L=City/O=IndexPilot/CN=localhost"

# Generate self-signed certificate (valid for 1 year)
openssl x509 -req -days 365 -in server.csr -signkey server.key -out server.crt

# Set proper permissions (Linux/Mac)
chmod 600 server.key
chmod 644 server.crt

# Clean up CSR
rm server.csr
```

**For Windows (Git Bash or WSL):**
```bash
# Same commands work in Git Bash or WSL
# Or use OpenSSL for Windows: https://slproweb.com/products/Win32OpenSSL.html
```

### Step 2: Update docker-compose.yml

Uncomment SSL configuration:

```yaml
services:
  postgres:
    environment:
      POSTGRES_SSL: on  # Enable SSL
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./ssl:/var/lib/postgresql/ssl:ro  # Mount SSL certificates
    command: >
      postgres
      -c ssl=on
      -c ssl_cert_file=/var/lib/postgresql/ssl/server.crt
      -c ssl_key_file=/var/lib/postgresql/ssl/server.key
      # ... other memory settings ...
```

### Step 3: Update Connection String

Update your connection to use SSL:

```bash
# Environment variable
export DB_SSLMODE=require

# Or in connection string
export SUPABASE_DB_URL=postgresql://user:pass@host:5432/db?sslmode=require
```

### Step 4: Restart PostgreSQL

```bash
docker-compose restart postgres
```

---

## Option 2: CA-Signed Certificates (Production)

### Step 1: Get Certificates from CA

**Commercial CA (e.g., Let's Encrypt, DigiCert):**
1. Purchase or obtain certificate from CA
2. Download certificate files
3. Place in `ssl/` directory

**Self-Hosted CA:**
1. Set up your own Certificate Authority
2. Generate certificates signed by your CA
3. Distribute CA certificate to clients

### Step 2: Configure PostgreSQL

Same as Option 1, but use CA-signed certificates:

```yaml
volumes:
  - ./ssl:/var/lib/postgresql/ssl:ro
command: >
  postgres
  -c ssl=on
  -c ssl_cert_file=/var/lib/postgresql/ssl/server.crt
  -c ssl_key_file=/var/lib/postgresql/ssl/server.key
  -c ssl_ca_file=/var/lib/postgresql/ssl/ca.crt  # CA certificate
```

---

## Option 3: Cloud Provider SSL (Recommended)

### AWS RDS

**Automatic SSL:**
- RDS provides SSL certificates automatically
- Download CA certificate: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html
- Connection string includes `?sslmode=require`

### Google Cloud SQL

**Automatic SSL:**
- Cloud SQL provides SSL certificates
- Download client certificate from Cloud Console
- Use Cloud SQL Proxy for secure connections

### Azure Database for PostgreSQL

**Automatic SSL:**
- Azure enforces SSL by default
- Download CA certificate from Azure Portal
- Connection string includes `?sslmode=require`

---

## Verification

### Check SSL Status

```sql
-- In PostgreSQL
SHOW ssl;
SHOW ssl_cert_file;
SHOW ssl_key_file;
```

### Test Connection with SSL

```python
from src.db import get_connection

# Connection should use SSL if configured
with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SHOW ssl")
    ssl_status = cursor.fetchone()[0]
    print(f"SSL enabled: {ssl_status}")
```

### Check Connection String

```bash
# Should include sslmode=require
echo $DB_SSLMODE
```

---

## Troubleshooting

### Certificate Errors

**Error**: "SSL connection has been closed unexpectedly"
- **Fix**: Check certificate file paths and permissions
- **Fix**: Ensure certificate is not expired

**Error**: "certificate verify failed"
- **Fix**: For self-signed, use `sslmode=prefer` instead of `require`
- **Fix**: For CA-signed, ensure CA certificate is trusted

### Permission Errors

**Error**: "Permission denied" when reading certificate
- **Fix**: Set proper file permissions (600 for key, 644 for cert)
- **Fix**: Ensure Docker can read files (check volume mount)

### Windows-Specific Issues

**Issue**: OpenSSL not available
- **Fix**: Install OpenSSL for Windows: https://slproweb.com/products/Win32OpenSSL.html
- **Fix**: Use WSL (Windows Subsystem for Linux)
- **Fix**: Use Git Bash (includes OpenSSL)

---

## Security Best Practices

1. **Never commit certificates to git**
   - Add `ssl/` to `.gitignore`
   - Use environment variables for production certificates

2. **Use strong keys**
   - Minimum 2048-bit RSA keys
   - Consider 4096-bit for production

3. **Rotate certificates regularly**
   - Self-signed: Regenerate annually
   - CA-signed: Follow CA expiration schedule

4. **Restrict file permissions**
   - Private keys: 600 (owner read/write only)
   - Certificates: 644 (owner read/write, others read)

5. **Use environment variables for production**
   - Never hardcode certificate paths
   - Use secrets management (AWS Secrets Manager, HashiCorp Vault, etc.)

---

## Quick Start (Self-Signed for Development)

```bash
# 1. Generate certificates
mkdir -p ssl
cd ssl
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr -subj "/CN=localhost"
openssl x509 -req -days 365 -in server.csr -signkey server.key -out server.crt
rm server.csr
cd ..

# 2. Update docker-compose.yml (uncomment SSL lines)

# 3. Restart PostgreSQL
docker-compose restart postgres

# 4. Test connection
python -c "from src.db import get_connection; conn = get_connection(); print('SSL connection successful')"
```

---

## Summary

**For Development:**
- Use self-signed certificates (Option 1)
- Quick to set up
- Good for local testing

**For Production:**
- Use cloud provider SSL (Option 3) - **Recommended**
- Or CA-signed certificates (Option 2)
- Never use self-signed in production

**Current Status:**
- SSL is **disabled** by default (commented out in docker-compose.yml)
- Enable by uncommenting SSL configuration lines
- Generate certificates using OpenSSL

