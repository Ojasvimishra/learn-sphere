"""
LearnSphere - Database Connection Layer (Tier 3)
High-performance MongoDB connection pooling using PyMongo.
Configured with sensible dev/production connection pool limits.
"""

import os
import threading
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

load_dotenv()


class MongoConnectionManager:
    """
    Singleton connection manager providing thread-safe access
    to the MongoDB database with optimized connection pooling.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        if MongoConnectionManager._instance is not None:
            raise RuntimeError("Use MongoConnectionManager.get_instance() instead.")

        self.uri = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017/")
        self.db_name = os.getenv("MONGODB_NAME", "learnsphere_db")
        # Sensible dev defaults: max 20, min 2; override via env in high-concurrency production
        self.max_pool_size = int(os.getenv("MONGODB_MAX_POOL_SIZE", "20"))
        self.min_pool_size = int(os.getenv("MONGODB_MIN_POOL_SIZE", "2"))
        self.timeout_ms = int(os.getenv("MONGODB_TIMEOUT_MS", "5000"))

        self._client = None
        self._db = None
        self._init_client()

    def _init_client(self):
        """Initializes PyMongo client with optimized connection pooling."""
        try:
            self._client = MongoClient(
                self.uri,
                maxPoolSize=self.max_pool_size,
                minPoolSize=self.min_pool_size,
                maxIdleTimeMS=45000,
                waitQueueTimeoutMS=self.timeout_ms,
                serverSelectionTimeoutMS=self.timeout_ms,
                connectTimeoutMS=self.timeout_ms,
                socketTimeoutMS=10000,
                retryWrites=True,
                retryReads=True,
                appname="LearnSphere-Backend"
            )
            self._db = self._client[self.db_name]
        except Exception as e:
            self._client = None
            self._db = None
            raise ConnectionFailure(f"Failed to connect to MongoDB: {str(e)}")

    @classmethod
    def get_instance(cls):
        """Thread-safe singleton accessor."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def db(self):
        """Returns active database handle."""
        if self._db is None or self._client is None:
            with self._lock:
                self._init_client()
        return self._db

    @property
    def client(self):
        """Returns PyMongo client instance."""
        return self._client

    def ping(self) -> bool:
        """Pings the MongoDB server to verify health."""
        try:
            res = self.client.admin.command('ping')
            return bool(res.get('ok') == 1.0)
        except (ConnectionFailure, ServerSelectionTimeoutError):
            return False

    def close(self):
        """Closes all active pooled connections."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None


# Global helper functions
def get_db():
    """Convenience accessor for database instance."""
    return MongoConnectionManager.get_instance().db


def get_collection(name: str):
    """Convenience accessor for specific collection."""
    return MongoConnectionManager.get_instance().db[name]
