#!/bin/bash
# Download test databases for IndexPilot benchmarking
# Date: 08-12-2025

set -e

DATASETS_DIR="../../data/benchmarking"
mkdir -p "$DATASETS_DIR"

echo "Downloading test databases for IndexPilot..."

# 1. Employees Database
echo "Downloading Employees database..."
if [ ! -f "$DATASETS_DIR/employees_db-full-1.0.6.tar.bz2" ]; then
    curl -L -o "$DATASETS_DIR/employees_db-full-1.0.6.tar.bz2" \
        "https://github.com/datacharmer/test_db/archive/refs/heads/master.zip" || \
    curl -L -o "$DATASETS_DIR/employees_db-full-1.0.6.tar.bz2" \
        "https://github.com/datacharmer/test_db/releases/download/v1.0.7/test_db-1.0.7.tar.gz"
    echo "✅ Employees database downloaded"
else
    echo "✅ Employees database already downloaded"
fi

# 2. Sakila Database (PostgreSQL version)
echo "Downloading Sakila database..."
if [ ! -f "$DATASETS_DIR/sakila-pg.zip" ]; then
    # Try multiple sources
    curl -L -o "$DATASETS_DIR/sakila-pg.zip" \
        "https://www.postgresqltutorial.com/wp-content/uploads/2019/05/dvdrental.zip" || \
    curl -L -o "$DATASETS_DIR/sakila-pg.zip" \
        "https://dev.mysql.com/doc/sakila/en/sakila-installation.html" || \
    echo "⚠️  Sakila download failed. Please download manually from:"
    echo "   https://www.postgresqltutorial.com/postgresql-sample-database/"
    echo "   Or: https://dev.mysql.com/doc/sakila/en/"
else
    echo "✅ Sakila database already downloaded"
fi

# 3. World Database (PostgreSQL)
echo "Downloading World database..."
if [ ! -f "$DATASETS_DIR/world.sql" ]; then
    curl -L -o "$DATASETS_DIR/world.sql" \
        "https://www.postgresqltutorial.com/wp-content/uploads/2019/05/world.sql" || \
    echo "⚠️  World database download failed. Please download manually from:"
    echo "   https://www.postgresqltutorial.com/postgresql-sample-database/"
else
    echo "✅ World database downloaded"
fi

echo ""
echo "✅ Download complete!"
echo "Next steps:"
echo "  1. Extract archives: cd datasets && unzip sakila-pg.zip"
echo "  2. Run setup scripts: python scripts/setup_sakila.py"
echo "  3. See docs/testing/DATASET_SETUP.md for details"

