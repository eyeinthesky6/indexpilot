#!/usr/bin/env python3
"""Test index_cleanup to find the error"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.db import get_connection
from psycopg2.extras import RealDictCursor

try:
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Test the exact query from index_cleanup.py
        print("Testing query...")
        cursor.execute(
            """
            SELECT
                schemaname,
                relname as tablename,
                indexrelname as indexname,
                idx_scan as index_scans,
                idx_tup_read as tuples_read,
                idx_tup_fetch as tuples_fetched,
                pg_relation_size(indexrelid) as index_size_bytes
            FROM pg_stat_user_indexes
            WHERE schemaname = 'public'
              AND indexrelname LIKE 'idx_%'
              AND idx_scan < %s
            ORDER BY idx_scan ASC, indexrelname
            LIMIT 5
        """,
            (10,),
        )
        
        results = cursor.fetchall()
        print(f"SUCCESS: Query works! Found {len(results)} indexes")
        if results:
            print(f"First result: {results[0]}")
        
        cursor.close()
        
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

