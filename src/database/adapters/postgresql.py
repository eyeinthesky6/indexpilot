"""PostgreSQL database adapter"""


from src.database.adapters.base import DatabaseAdapter


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL-specific database adapter"""

    def get_auto_increment_type(self) -> str:
        """Return PostgreSQL auto-increment type"""
        return "SERIAL"

    def get_json_type(self) -> str:
        """Return PostgreSQL JSON type"""
        return "JSONB"

    def create_index_sql(
        self,
        table: str,
        fields: list[str],
        index_type: str = 'btree',
        index_name: str | None = None
    ) -> str:
        """
        Generate PostgreSQL CREATE INDEX SQL.

        Args:
            table: Table name
            fields: List of field names to index
            index_type: Index type (btree, hash, gin, gist, brin)
            index_name: Optional index name

        Returns:
            str: CREATE INDEX SQL statement
        """
        if not fields:
            raise ValueError("At least one field is required for index")

        # Generate index name if not provided
        if index_name is None:
            field_names = '_'.join(fields)
            index_name = f"idx_{table}_{field_names}"

        # Escape identifiers
        escaped_table = self.escape_identifier(table)
        escaped_fields = [self.escape_identifier(f) for f in fields]
        escaped_index_name = self.escape_identifier(index_name)

        # Build SQL
        fields_str = ', '.join(escaped_fields)
        sql = f"CREATE INDEX IF NOT EXISTS {escaped_index_name} ON {escaped_table} USING {index_type} ({fields_str})"

        return sql

    def get_table_size_query(self, table: str) -> str:
        """Get PostgreSQL query for table size"""
        escaped_table = self.escape_identifier(table)
        return f"SELECT pg_relation_size({escaped_table!r})"

    def get_table_index_size_query(self, table: str) -> str:
        """Get PostgreSQL query for total index size"""
        escaped_table = self.escape_identifier(table)
        return f"""
            SELECT COALESCE(SUM(pg_relation_size(indexrelid)), 0)
            FROM pg_index
            WHERE indrelid = {escaped_table!r}::regclass
        """

    def get_table_row_count_query(self, table: str) -> str:
        """Get PostgreSQL query for row count"""
        escaped_table = self.escape_identifier(table)
        return f"SELECT COUNT(*) FROM {escaped_table}"

    def escape_identifier(self, identifier: str) -> str:
        """
        Escape PostgreSQL identifier.

        PostgreSQL uses double quotes for identifiers.
        """
        # Remove any existing quotes
        identifier = identifier.strip('"')
        # Escape double quotes inside identifier
        identifier = identifier.replace('"', '""')
        # Wrap in double quotes
        return f'"{identifier}"'

    def get_database_type(self) -> str:
        """Return PostgreSQL database type"""
        return "postgresql"

