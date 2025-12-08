#!/bin/bash
# Production backup script for IndexPilot
# Backs up database and configuration files

set -e  # Exit on any error

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
DATE=$(date +%Y%m%d_%H%M%S)
DB_BACKUP_FILE="${BACKUP_DIR}/db_backup_${DATE}.sql"
CONFIG_BACKUP_FILE="${BACKUP_DIR}/config_backup_${DATE}.yaml"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "🔄 IndexPilot Production Backup"
echo "================================"
echo ""

# Get database configuration from environment
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-indexpilot}"
DB_USER="${DB_USER:-indexpilot}"
DB_PASSWORD="${DB_PASSWORD}"

if [ -z "$DB_PASSWORD" ]; then
    echo "❌ Error: DB_PASSWORD environment variable is required"
    exit 1
fi

# Set PGPASSWORD for pg_dump
export PGPASSWORD="$DB_PASSWORD"

# Backup database
echo "1. Backing up database..."
if command -v pg_dump &> /dev/null; then
    pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        --no-owner --no-acl \
        > "$DB_BACKUP_FILE"
    
    if [ $? -eq 0 ]; then
        DB_SIZE=$(du -h "$DB_BACKUP_FILE" | cut -f1)
        echo "   ✅ Database backup created: $DB_BACKUP_FILE ($DB_SIZE)"
    else
        echo "   ❌ Database backup failed"
        exit 1
    fi
else
    echo "   ⚠️  pg_dump not found, skipping database backup"
fi

# Backup configuration
echo ""
echo "2. Backing up configuration..."
if [ -f "indexpilot_config.yaml" ]; then
    cp "indexpilot_config.yaml" "$CONFIG_BACKUP_FILE"
    echo "   ✅ Configuration backup created: $CONFIG_BACKUP_FILE"
else
    echo "   ⚠️  indexpilot_config.yaml not found, skipping config backup"
fi

# Backup environment file (if exists)
if [ -f ".env.production" ]; then
    ENV_BACKUP_FILE="${BACKUP_DIR}/env_backup_${DATE}.env"
    cp ".env.production" "$ENV_BACKUP_FILE"
    echo "   ✅ Environment file backup created: $ENV_BACKUP_FILE"
fi

# Clean up old backups (keep last 30 days)
echo ""
echo "3. Cleaning up old backups (keeping last 30 days)..."
find "$BACKUP_DIR" -name "db_backup_*.sql" -mtime +30 -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "config_backup_*.yaml" -mtime +30 -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "env_backup_*.env" -mtime +30 -delete 2>/dev/null || true
echo "   ✅ Old backups cleaned"

# Summary
echo ""
echo "================================"
echo "✅ Backup completed successfully!"
echo ""
echo "Backup location: $BACKUP_DIR"
echo "Database backup: $DB_BACKUP_FILE"
echo "Config backup: $CONFIG_BACKUP_FILE"
echo ""
echo "To restore database:"
echo "  psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME < $DB_BACKUP_FILE"
echo ""

# Unset PGPASSWORD for security
unset PGPASSWORD

