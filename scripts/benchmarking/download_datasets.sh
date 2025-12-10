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
if [ ! -f "$DATASETS_DIR/sakila-complete.sql" ]; then
    # Try GitHub source (working alternative)
    curl -L -o "$DATASETS_DIR/sakila-schema.sql" \
        "https://raw.githubusercontent.com/jOOQ/jOOQ/main/jOOQ-examples/Sakila/postgres-sakila-db/postgres-sakila-schema.sql" && \
    curl -L -o "$DATASETS_DIR/sakila-data.sql" \
        "https://raw.githubusercontent.com/jOOQ/jOOQ/main/jOOQ-examples/Sakila/postgres-sakila-db/postgres-sakila-insert-data.sql" && \
    cat "$DATASETS_DIR/sakila-schema.sql" "$DATASETS_DIR/sakila-data.sql" > "$DATASETS_DIR/sakila-complete.sql" && \
    rm "$DATASETS_DIR/sakila-schema.sql" "$DATASETS_DIR/sakila-data.sql" && \
    echo "✅ Sakila database downloaded from GitHub" || \
    echo "⚠️  Sakila download failed. Please download manually from:"
    echo "   https://github.com/jOOQ/jOOQ/tree/main/jOOQ-examples/Sakila/postgres-sakila-db"
else
    echo "✅ Sakila database already downloaded"
fi

# 3. World Database (PostgreSQL)
echo "Downloading World database..."
if [ ! -f "$DATASETS_DIR/world.sql" ]; then
    # Create simple world database schema
    cat > "$DATASETS_DIR/world.sql" << 'EOF'
-- World Database Schema for IndexPilot Testing
-- Simple countries, cities, languages schema

CREATE TABLE country (
    code char(3) NOT NULL DEFAULT '',
    name text NOT NULL DEFAULT '',
    continent text NOT NULL DEFAULT 'Asia',
    region text NOT NULL DEFAULT '',
    surfacearea decimal(10,2) NOT NULL DEFAULT '0.00',
    indepyear smallint DEFAULT NULL,
    population int NOT NULL DEFAULT '0',
    lifeexpectancy decimal(3,1) DEFAULT NULL,
    gnp decimal(10,2) DEFAULT NULL,
    gnpold decimal(10,2) DEFAULT NULL,
    localname text NOT NULL DEFAULT '',
    governmentform text NOT NULL DEFAULT '',
    headofstate text DEFAULT NULL,
    capital int DEFAULT NULL,
    code2 char(2) NOT NULL DEFAULT '',
    PRIMARY KEY (code)
);

CREATE TABLE city (
    id int NOT NULL DEFAULT '0',
    name text NOT NULL DEFAULT '',
    countrycode char(3) NOT NULL DEFAULT '',
    district text NOT NULL DEFAULT '',
    population int NOT NULL DEFAULT '0',
    PRIMARY KEY (id)
);

CREATE TABLE countrylanguage (
    countrycode char(3) NOT NULL DEFAULT '',
    language text NOT NULL DEFAULT '',
    isofficial boolean NOT NULL DEFAULT false,
    percentage decimal(4,1) NOT NULL DEFAULT '0.0',
    PRIMARY KEY (countrycode,language)
);

-- Sample data
INSERT INTO country (code, name, continent, region, population, capital, code2) VALUES
('USA', 'United States', 'North America', 'North America', 331900000, 1, 'US'),
('IND', 'India', 'Asia', 'Southern and Central Asia', 1380004385, 2, 'IN'),
('CHN', 'China', 'Asia', 'Eastern Asia', 1439323776, 3, 'CN'),
('BRA', 'Brazil', 'South America', 'South America', 212559417, 4, 'BR'),
('RUS', 'Russia', 'Europe', 'Eastern Europe', 145934462, 5, 'RU');

INSERT INTO city (id, name, countrycode, district, population) VALUES
(1, 'Washington', 'USA', 'District of Columbia', 689545),
(2, 'New Delhi', 'IND', 'Delhi', 257803),
(3, 'Beijing', 'CHN', 'Beijing', 21540000),
(4, 'Brasília', 'BRA', 'Distrito Federal', 3015268),
(5, 'Moscow', 'RUS', 'Moscow (City)', 12506468);

INSERT INTO countrylanguage (countrycode, language, isofficial, percentage) VALUES
('USA', 'English', true, 79.2),
('IND', 'Hindi', true, 41.0),
('IND', 'English', false, 12.1),
('CHN', 'Chinese', true, 92.0),
('BRA', 'Portuguese', true, 97.5),
('RUS', 'Russian', true, 96.3);
EOF
    echo "✅ World database created"
else
    echo "✅ World database already exists"
fi

echo ""
echo "✅ Download complete!"
echo "Next steps:"
echo "  1. Extract archives: cd datasets && unzip sakila-pg.zip"
echo "  2. Run setup scripts: python scripts/setup_sakila.py"
echo "  3. See docs/testing/DATASET_SETUP.md for details"

