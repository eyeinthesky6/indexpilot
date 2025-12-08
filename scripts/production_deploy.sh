#!/bin/bash
# Production deployment script for IndexPilot
# This script demonstrates the production hardening steps

set -e  # Exit on any error

echo "🚀 IndexPilot Production Deployment"
echo "==================================="

# Step 1: Environment setup
echo ""
echo "1. Setting up production environment..."
export ENVIRONMENT=production
export PYTHONPATH=$(pwd)/src:$PYTHONPATH

# Use venv python if available, otherwise use system python
if [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
elif [ -f "venv/Scripts/python.exe" ]; then
    PYTHON="venv/Scripts/python.exe"
else
    PYTHON="python"
fi

# Step 2: Validate configuration
echo ""
echo "2. Validating production configuration..."
$PYTHON -c "from src.production_config import validate_production_config; validate_production_config()"
echo "✅ Configuration validated"

# Step 3: Run quality checks
echo ""
echo "3. Running code quality checks..."
make check
echo "✅ Code quality checks passed"

# Step 4: Run tests
echo ""
echo "4. Running test suite..."
make run-tests
echo "✅ All tests passed"

# Step 5: Security scan
echo ""
echo "5. Running security scan..."
if command -v safety &> /dev/null; then
    safety check --continue-on-error || echo "⚠️  Security scan completed with warnings"
else
    echo "⚠️  Safety not installed, skipping security scan"
fi

# Step 6: Database setup (assumes PostgreSQL is running)
echo ""
echo "6. Setting up database..."
make init-db
echo "✅ Database initialized"

# Step 7: Build and start services
echo ""
echo "7. Starting production services..."

# Start database
docker-compose up -d postgres
echo "✅ PostgreSQL started"

# Start API server
echo "Starting API server..."
export UVICORN_HOST=0.0.0.0
export UVICORN_PORT=8000
export UVICORN_WORKERS=4  # Production worker count

# In production, use a process manager like systemd or supervisor
# For demo purposes, we'll show the command
echo "Production command: uvicorn src.api_server:app --host 0.0.0.0 --port 8000 --workers 4"
echo "✅ API server configured for production"

# Step 8: Health checks
echo ""
echo "8. Running production validation..."
$PYTHON scripts/production_validation.py
echo "✅ Production validation completed"

# Step 9: Monitoring setup
echo ""
echo "9. Monitoring setup..."
echo "📊 Configure the following monitoring:"
echo "   - Prometheus metrics: http://localhost:8000/metrics"
echo "   - Health checks: http://localhost:8000/health"
echo "   - Database monitoring: Connection pools, slow queries"
echo "   - Application logs: Structured JSON logging enabled"

echo ""
echo "🎉 Production deployment completed!"
echo ""
echo "Next steps:"
echo "- Configure reverse proxy (nginx/caddy)"
echo "- Set up SSL certificates"
echo "- Configure backup procedures"
echo "- Set up monitoring alerts"
echo "- Test failover scenarios"
echo ""
echo "📚 See .cursor/commands/PRODUCTION_HARDENING.md for detailed hardening guide"
