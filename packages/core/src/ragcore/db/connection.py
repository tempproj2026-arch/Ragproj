from psycopg_pool import ConnectionPool
from contextlib import contextmanager
from pgvector.psycopg import register_vector
from ..config import settings

class Database:
    _pool: ConnectionPool | None = None
    
    @classmethod
    def init_pool(cls, role: str = "ingest"):
        if cls._pool is None:
            db_url = settings.get_db_url(role)
            # Use connection pool for performance
            cls._pool = ConnectionPool(db_url, min_size=1, max_size=5)
            
    @classmethod
    def close(cls):
        if cls._pool is not None:
            cls._pool.close()
            cls._pool = None

    @classmethod
    @contextmanager
    def get_connection(cls):
        if cls._pool is None:
            cls.init_pool()
        # Acquire a connection from the pool
        with cls._pool.connection() as conn:
            # Register pgvector types for this connection
            register_vector(conn)
            yield conn
