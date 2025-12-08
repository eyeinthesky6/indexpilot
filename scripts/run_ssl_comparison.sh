#!/bin/bash
# Simple script to run SSL comparison tests

set -e

echo "=========================================="
echo "SSL Performance Comparison Test"
echo "=========================================="
echo ""

# Save current docker-compose.yml
cp docker-compose.yml docker-compose.yml.backup

echo "Step 1: Running CRM simulation WITHOUT SSL..."
python -m src.simulation.simulator autoindex --scenario small > results_crm_no_ssl.txt 2>&1
echo "  Done. Results: results_crm_no_ssl.txt"

echo ""
echo "Step 2: Running Stock data simulation WITHOUT SSL..."
python -m src.simulation.simulator real-data --scenario small --stocks WIPRO,TCS,ITC --queries 200 > results_stock_no_ssl.txt 2>&1
echo "  Done. Results: results_stock_no_ssl.txt"

echo ""
echo "Step 3: Enabling SSL in docker-compose.yml..."
# Disable SSL first to restore clean state
sed -i 's/POSTGRES_SSL: on/# POSTGRES_SSL: on/' docker-compose.yml
sed -i 's|- ./ssl:/var/lib/postgresql/ssl:ro|# - ./ssl:/var/lib/postgresql/ssl:ro|' docker-compose.yml

# Enable SSL properly
sed -i 's/# POSTGRES_SSL: on/POSTGRES_SSL: on/' docker-compose.yml
sed -i 's|# - ./ssl:/var/lib/postgresql/ssl:ro|- ./ssl:/var/lib/postgresql/ssl:ro|' docker-compose.yml

# Update command to include SSL
python -c "
import yaml
with open('docker-compose.yml', 'r') as f:
    doc = yaml.safe_load(f)

cmd = doc['services']['postgres']['command']
if isinstance(cmd, str):
    cmd = cmd.split('\n')

# Add SSL params if not present
new_cmd = ['postgres', '-c', 'ssl=on', '-c', 'ssl_cert_file=/var/lib/postgresql/ssl/server.crt', '-c', 'ssl_key_file=/var/lib/postgresql/ssl/server.key']
# Add existing memory params
if isinstance(cmd, list):
    for line in cmd:
        if line.strip() and 'shared_buffers' in line:
            new_cmd.extend(['-c', line.split('=')[1].strip()])
        elif line.strip() and 'maintenance_work_mem' in line:
            new_cmd.extend(['-c', line.split('=')[1].strip()])
        elif line.strip() and 'work_mem' in line:
            new_cmd.extend(['-c', line.split('=')[1].strip()])
        elif line.strip() and 'effective_cache_size' in line:
            new_cmd.extend(['-c', line.split('=')[1].strip()])
        elif line.strip() and 'max_connections' in line:
            new_cmd.extend(['-c', line.split('=')[1].strip()])

doc['services']['postgres']['command'] = ' '.join(new_cmd)

with open('docker-compose.yml', 'w') as f:
    yaml.safe_dump(doc, f, default_flow_style=False)
"

echo "  SSL enabled. Restarting PostgreSQL..."
docker-compose restart postgres
sleep 10

echo ""
echo "Step 4: Running CRM simulation WITH SSL..."
python -m src.simulation.simulator autoindex --scenario small > results_crm_with_ssl.txt 2>&1
echo "  Done. Results: results_crm_with_ssl.txt"

echo ""
echo "Step 5: Running Stock data simulation WITH SSL..."
python -m src.simulation.simulator real-data --scenario small --stocks WIPRO,TCS,ITC --queries 200 > results_stock_with_ssl.txt 2>&1
echo "  Done. Results: results_stock_with_ssl.txt"

echo ""
echo "=========================================="
echo "Comparison Summary"
echo "=========================================="
echo ""
echo "Extracting key metrics..."

# Extract metrics from results
extract_time() {
    grep -i "elapsed\|total.*time\|simulation.*complete" "$1" | tail -1 || echo "N/A"
}

echo ""
echo "CRM Schema:"
echo "  Without SSL: $(extract_time results_crm_no_ssl.txt)"
echo "  With SSL:    $(extract_time results_crm_with_ssl.txt)"

echo ""
echo "Stock Data:"
echo "  Without SSL: $(extract_time results_stock_no_ssl.txt)"
echo "  With SSL:    $(extract_time results_stock_with_ssl.txt)"

echo ""
echo "Full results saved in:"
echo "  - results_crm_no_ssl.txt"
echo "  - results_stock_no_ssl.txt"
echo "  - results_crm_with_ssl.txt"
echo "  - results_stock_with_ssl.txt"

# Restore original docker-compose.yml
echo ""
echo "Restoring original docker-compose.yml..."
mv docker-compose.yml.backup docker-compose.yml
docker-compose restart postgres

echo ""
echo "Done!"

