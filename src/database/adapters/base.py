"""Base database adapter interface"""

from abc import ABC, abstractmethod


class DatabaseAdapter(ABC):
    """Abstract base class for database adapters"""

    @abstractmethod
    def get_auto_increment_type(self) -> str:
        """
        Return auto-increment type for this database.

        Examples:
            PostgreSQL: "SERIAL"
            MySQL: "AUTO_INCREMENT"
            SQL Server: "IDENTITY(1,1)"
        """
        pass

    @abstractmethod
    def get_json_type(self) -> str:
        """
        Return JSON type for this database.

        Examples:
            PostgreSQL: "JSONB"
            MySQL: "JSON"
            SQL Server: "NVARCHAR(MAX)"
        """
        pass

    @abstractmethod
    def create_index_sql(
        self,
        table: str,
        fields: list[str],
        index_type: str = 'btree',
        index_name: str | None = None
    ) -> str:
        """
        Generate CREATE INDEX SQL statement.

        Args:
            table: Table name
            fields: List of field names to index
            index_type: Index type (btree, hash, etc.)
            index_name: Optional index name (auto-generated if None)

        Returns:
            str: CREATE INDEX SQL statement
        """
        pass

    @abstractmethod
    def get_table_size_query(self, table: str) -> str:
        """
        Get query to fetch table size in bytes.

        Args:
            table: Table name

        Returns:
            str: SQL query that returns table size
        """
        pass

    @abstractmethod
    def get_table_index_size_query(self, table: str) -> str:
        """
        Get query to fetch total index size for a table in bytes.

        Args:
            table: Table name

        Returns:
            str: SQL query that returns total index size
        """
        pass

    @abstractmethod
    def get_table_row_count_query(self, table: str) -> str:
        """
        Get query to fetch approximate row count for a table.

        Args:
            table: Table name

        Returns:
            str: SQL query that returns row count
        """
        pass

    @abstractmethod
    def escape_identifier(self, identifier: str) -> str:
        """
        Escape database identifier (table/column name).

        Args:
            identifier: Identifier to escape

        Returns:
            str: Escaped identifier
        """
        pass

    @abstractmethod
    def get_database_type(self) -> str:
        """
        Return database type identifier.

        Returns:
            str: Database type (e.g., 'postgresql', 'mysql', 'sqlserver')
        """
        pass

