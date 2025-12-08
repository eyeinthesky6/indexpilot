# Test file to verify unsafe access detection
# This file should be flagged by the check script

from src.db import get_connection

def test_unsafe_access():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        
        # UNSAFE: Direct tuple access
        version = cursor.fetchone()[0]  # Should be flagged
        
        # UNSAFE: Direct row access
        row = cursor.fetchone()
        value = row[0]  # Should be flagged
        
        return version, value

