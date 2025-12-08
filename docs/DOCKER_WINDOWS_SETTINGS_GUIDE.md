# Docker and Windows Settings Guide

**Date**: 08-12-2025  
**Status**: Guide for Docker and Windows-specific configuration

---

## Are Docker and Windows Settings Project-Specific?

### Docker Settings

**Project-Specific:**
- ✅ `docker-compose.yml` - **Project-specific** (in project root)
- ✅ PostgreSQL memory configuration - **Project-specific** (calculated per system)
- ✅ Volume mounts - **Project-specific** (project data)
- ✅ Port mappings - **Project-specific** (can customize)

**System-Wide:**
- ❌ Docker Desktop settings - **System-wide** (affects all containers)
- ❌ Docker daemon configuration - **System-wide**
- ❌ Windows shared memory limits - **System-wide** (OS-level)

### Windows Settings

**System-Wide (Affects All Applications):**
- ❌ Shared memory segment limits (~64MB per segment) - **System-wide**
- ❌ Registry settings - **System-wide**
- ❌ Windows memory management - **System-wide**

**Project-Specific:**
- ✅ PostgreSQL configuration - **Project-specific** (in docker-compose.yml)
- ✅ Application memory usage - **Project-specific** (configurable)

---

## Current System Status

### CPU Usage
- **Current**: 32.0% (normal for active system)
- **Cores**: 4 cores
- **Frequency**: 1190 MHz (likely power-saving mode)

### Memory Usage
- **Total**: 31.77 GB
- **Used**: 10.02 GB (31.5%)
- **Available**: 21.76 GB (plenty available!)

### PostgreSQL Memory Configuration
- **Auto-adjust**: ✅ Enabled
- **Target**: 8 GB (50% of available, capped at max)
- **Windows-aware**: ✅ Yes (maintenance_work_mem limited to 32MB)

---

## Docker Settings

### Project-Specific Settings (docker-compose.yml)

**Current Configuration:**
```yaml
services:
  postgres:
    image: postgres:15-alpine
    container_name: indexpilot_postgres  # Project-specific name
    ports:
      - "5432:5432"  # Can be changed if port conflict
    volumes:
      - postgres_data:/var/lib/postgresql/data  # Project-specific volume
    command: >
      postgres -c shared_buffers=1024MB ...  # Project-specific memory config
```

**What You Can Customize:**
- Port number (if 5432 is in use)
- Container name
- Volume names
- Memory settings (auto-calculated)
- Resource limits

### System-Wide Docker Settings

**Docker Desktop Settings (Windows):**
- **Location**: Docker Desktop → Settings
- **Affects**: All containers on your system
- **Settings**:
  - Memory allocation for Docker
  - CPU allocation for Docker
  - Disk image size
  - WSL 2 integration

**To Check/Adjust:**
1. Open Docker Desktop
2. Go to Settings → Resources
3. Adjust:
   - **Memory**: Recommended 4-8GB (you have 32GB, so plenty)
   - **CPUs**: Can use all 4 cores
   - **Disk**: Default is usually fine

---

## Windows Settings

### Shared Memory Limits (System-Wide)

**Current Limit:**
- **Per segment**: ~64MB (Windows default)
- **Total**: Limited by available RAM (you have 32GB, so plenty)

**Is This Project-Specific?**
- ❌ **No** - This is a **Windows OS-level limit**
- Affects all applications using shared memory
- Cannot be changed per-project
- Our code handles this by limiting `maintenance_work_mem` to 32MB

**Why We Can't Change It:**
- Requires Windows registry changes
- Affects entire system
- Requires system restart
- Can break other applications

**Our Solution:**
- ✅ Detect Windows automatically
- ✅ Limit `maintenance_work_mem` to 32MB (safe limit)
- ✅ Use more memory for `shared_buffers` (different mechanism)
- ✅ Gracefully handle errors when limit is hit

### Registry Settings (System-Wide)

**If you wanted to increase Windows shared memory (NOT RECOMMENDED):**

**Location**: `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Session Manager\SubSystems\Windows`

**Warning:**
- ⚠️ **DO NOT DO THIS** - Can break system
- ⚠️ Requires system restart
- ⚠️ Affects all applications
- ⚠️ Our code already handles the limit gracefully

**Better Solution:**
- ✅ Use our dynamic memory configuration (already implemented)
- ✅ It automatically limits `maintenance_work_mem` on Windows
- ✅ No system changes needed
- ✅ Project-specific and safe

---

## How to Fix/Adjust Settings

### 1. Docker Resource Limits (System-Wide)

**Increase Docker Memory Allocation:**

1. Open Docker Desktop
2. Settings → Resources → Advanced
3. Increase **Memory** slider (recommended: 4-8GB)
4. Click **Apply & Restart**

**This affects:**
- All Docker containers on your system
- Not project-specific

### 2. PostgreSQL Memory (Project-Specific)

**Adjust Memory Percentage:**

Edit `indexpilot_config.yaml`:
```yaml
features:
  memory_config:
    memory_percent: 50.0  # Change to 30.0 for less, 70.0 for more
    max_memory_mb: 8192   # Change max limit
```

Then update:
```bash
python scripts/update_postgres_memory_config.py
docker-compose restart postgres
```

**This affects:**
- Only this project's PostgreSQL container
- Project-specific

### 3. Port Conflicts (Project-Specific)

**If port 5432 is in use:**

Edit `docker-compose.yml`:
```yaml
ports:
  - "5433:5432"  # Use 5433 on host, 5432 in container
```

Update connection:
```bash
export DB_PORT=5433
```

**This affects:**
- Only this project
- Project-specific

---

## SSL Configuration

### Quick Start (Self-Signed for Development)

**Generate Certificates:**

**Windows:**
```bash
scripts\generate_ssl_certificates.bat
```

**Linux/Mac:**
```bash
bash scripts/generate_ssl_certificates.sh
```

**Or manually:**
```bash
mkdir ssl
cd ssl
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr -subj "/CN=localhost"
openssl x509 -req -days 365 -in server.csr -signkey server.key -out server.crt
rm server.csr
```

**Enable SSL in docker-compose.yml:**

Uncomment these lines:
```yaml
environment:
  POSTGRES_SSL: on  # Uncomment this

volumes:
  - ./ssl:/var/lib/postgresql/ssl:ro  # Uncomment this

command: >
  postgres
  -c ssl=on
  -c ssl_cert_file=/var/lib/postgresql/ssl/server.crt
  -c ssl_key_file=/var/lib/postgresql/ssl/server.key
  # ... other settings ...
```

**Restart PostgreSQL:**
```bash
docker-compose restart postgres
```

**Where to Get Certificates:**

1. **Self-Signed (Development)**: Use script above
2. **CA-Signed (Production)**: 
   - Purchase from commercial CA (DigiCert, GlobalSign, etc.)
   - Use Let's Encrypt (free, automated)
   - Use cloud provider certificates (AWS, GCP, Azure)
3. **Cloud Databases**: Certificates provided automatically

**See**: `docs/SSL_CONFIGURATION_GUIDE.md` for detailed instructions

---

## Summary

### What's Project-Specific ✅
- `docker-compose.yml` configuration
- PostgreSQL memory settings (auto-calculated)
- Port mappings
- Volume names
- SSL certificates (in `ssl/` directory)

### What's System-Wide ❌
- Docker Desktop resource limits
- Windows shared memory limits
- Windows registry settings
- Docker daemon configuration

### Current Status ✅
- **Memory config**: Working correctly
- **CPU usage**: 32% (normal)
- **Available RAM**: 21.76 GB (plenty)
- **Windows limits**: Handled automatically
- **No errors**: All files verified

### Recommendations

1. **Docker Desktop**: Allocate 4-8GB memory (you have 32GB, so plenty)
2. **PostgreSQL**: Current settings are optimal (auto-calculated)
3. **SSL**: Use self-signed for development, CA-signed for production
4. **Windows limits**: Already handled by code (no changes needed)

Everything is working correctly! The system automatically handles Windows limits and uses your available RAM efficiently.

