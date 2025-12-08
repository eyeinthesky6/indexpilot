#!/usr/bin/env python3
"""Test index_cleanup with different cursor types"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.db import get_connection

try:
    with get_connection() as conn:
        # Try with regular cursor first
        print("Testing with regular cursor...")
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                schemaname,
                relname as tablename,
                indexrelname as indexname,
                idx_scan as index_scans
            FROM pg_stat_user_indexes
            WHERE schemaname = 'public'
              AND indexrelname LIKE 'idx_%'
              AND idx_scan < %s
            LIMIT 5
        """,
            (10,),
        )
        results = cursor.fetchall()
        print(f"Regular cursor: SUCCESS - {len(results)} results")
        cursor.close()
        
        # Try with RealDictCursor
        print("\nTesting with RealDictCursor...")
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT
                schemaname,
                relname as tablename,
                indexrelname as indexname,
                idx_scan as index_scans
            FROM pg_stat_user_indexes
            WHERE schemaname = 'public'
              AND indexrelname LIKE 'idx_%'
              AND idx_scan < %s
            LIMIT 5
        """,
            (10,),
        )
        results = cursor.fetchall()
        print(f"RealDictCursor: SUCCESS - {len(results)} results")
        cursor.close()
        
        # Try with full query
        print("\nTesting full query with RealDictCursor...")
        cursor = conn.cursor(cursor_factory=RealDictCursor)
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
        print(f"Full query: SUCCESS - {len(results)} results")
        if results:
            print(f"First result keys: {list(results[0].keys())}")
        cursor.close()
        
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

