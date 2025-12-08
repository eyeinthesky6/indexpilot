#!/usr/bin/env python3
"""Test pg_stat_user_indexes structure"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.db import get_connection

with get_connection() as conn:
    cursor = conn.cursor()
    # Get column names
    cursor.execute("SELECT * FROM pg_stat_user_indexes LIMIT 0")
    print("pg_stat_user_indexes columns:")
    for i, desc in enumerate(cursor.description):
        print(f"  {i}: {desc[0]}")
    cursor.close()
    
    # Try a simple query
    cursor = conn.cursor()
    cursor.execute("SELECT schemaname, relname, indexrelname, idx_scan FROM pg_stat_user_indexes LIMIT 1")
    result = cursor.fetchone()
    print(f"\nSimple query result: {result}")
    cursor.close()

