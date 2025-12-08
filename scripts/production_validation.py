#!/usr/bin/env python3
"""Production validation script for IndexPilot deployment."""

import os
import sys
from pathlib import Path

def check_environment_variables():
    """Check required production environment variables."""
    required_vars = {
        'ENVIRONMENT': 'production',
        'DB_PASSWORD': None,  # Any non-empty value
        'DB_HOST': None,
        'DB_SSLMODE': 'require'
    }

    missing = []
    invalid = []

    for var, expected in required_vars.items():
        value = os.getenv(var)
        if not value:
            missing.append(var)
        elif expected and value != expected:
            invalid.append(f"{var}={value} (expected {expected})")

    return missing, invalid

def check_database_connection():
    """Test database connectivity."""
    try:
        from src.db import get_connection
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            print(f"✅ Database connected: {version[:50]}...")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def check_api_health():
    """Test API health endpoint."""
    try:
        import requests
        response = requests.get("http://localhost:8000/", timeout=5)
        if response.status_code == 200:
            print("✅ API health check passed")
            return True
        else:
            print(f"❌ API returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API health check failed: {e}")
        return False

def check_security_headers():
    """Check for security headers in API responses."""
    try:
        import requests
        response = requests.get("http://localhost:8000/", timeout=5)
        headers = response.headers

        security_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options',
            'X-XSS-Protection',
            'Strict-Transport-Security'
        ]

        missing = [h for h in security_headers if h not in headers]
        if missing:
            print(f"⚠️  Missing security headers: {missing}")
        else:
            print("✅ Security headers present")

        return len(missing) == 0
    except Exception as e:
        print(f"❌ Security header check failed: {e}")
        return False

def main():
    """Run all production validation checks."""
    print("🔍 IndexPilot Production Validation")
    print("=" * 50)

    # Check environment variables
    print("\n1. Environment Variables:")
    missing, invalid = check_environment_variables()
    if missing:
        print(f"❌ Missing required variables: {missing}")
        return False
    if invalid:
        print(f"❌ Invalid variables: {invalid}")
        return False
    print("✅ Environment variables configured correctly")

    # Check database connection
    print("\n2. Database Connection:")
    if not check_database_connection():
        return False

    # Check API health
    print("\n3. API Health:")
    if not check_api_health():
        return False

    # Check security headers
    print("\n4. Security Headers:")
    check_security_headers()  # Warning only

    print("\n" + "=" * 50)
    print("🎉 Production validation completed successfully!")
    print("\nNext steps:")
    print("- Configure monitoring (Prometheus/Grafana)")
    print("- Set up log aggregation")
    print("- Configure backup procedures")
    print("- Test load balancing if applicable")

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
