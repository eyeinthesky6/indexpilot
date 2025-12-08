"""Type stubs for psycopg2.pool - Connection pooling"""

from psycopg2.connection import connection

class PoolError(Exception):
    """Base exception for pool errors"""

    pass

class ThreadedConnectionPool:
    """Thread-safe connection pool"""

    def __init__(
        self,
        minconn: int,
        maxconn: int,
        *args: object,
        **kwargs: object,
    ) -> None: ...
    def getconn(self, key: object = None) -> connection: ...
    def putconn(self, conn: connection, close: bool = False, key: object = None) -> None: ...
    def closeall(self) -> None: ...
    @property
    def minconn(self) -> int: ...
    @property
    def maxconn(self) -> int: ...
