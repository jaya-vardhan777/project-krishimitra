"""
Database session management and connection utilities for KrishiMitra platform.

This module provides session management, connection pooling, and database
initialization utilities for the application.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator
import logging

from .dynamodb_client import DynamoDBClient
from .schemas import DynamoDBSchemas
from ..config import get_settings

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Database session manager for KrishiMitra platform.
    
    Manages DynamoDB connections, session lifecycle, and provides
    utilities for database operations across the application.
    """
    
    _instance: Optional['SessionManager'] = None
    _dynamodb_client: Optional[DynamoDBClient] = None
    
    def __new__(cls) -> 'SessionManager':
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize session manager."""
        if not hasattr(self, '_initialized'):
            self.settings = get_settings()
            self._initialized = True
            logger.info("SessionManager initialized")
    
    @property
    def dynamodb_client(self) -> DynamoDBClient:
        """Get or create DynamoDB client instance."""
        if self._dynamodb_client is None:
            self._dynamodb_client = DynamoDBClient(region_name=self.settings.aws_region)
        return self._dynamodb_client
    
    async def initialize_database(self) -> bool:
        """Initialize database tables and connections."""
        try:
            logger.info("Initializing database...")
            
            # Create DynamoDB tables if they don't exist
            success = DynamoDBSchemas.create_all_tables(self.dynamodb_client.dynamodb)
            
            if success:
                logger.info("Database initialization completed successfully")
                return True
            else:
                logger.error("Database initialization failed")
                return False
                
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Perform health check on all database connections."""
        try:
            # Check DynamoDB connection
            dynamodb_healthy = self.dynamodb_client.health_check()
            
            if dynamodb_healthy:
                logger.debug("All database connections healthy")
                return True
            else:
                logger.warning("Some database connections unhealthy")
                return False
                
        except Exception as e:
            logger.error(f"Database health check error: {e}")
            return False
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[DynamoDBClient, None]:
        """
        Get database session context manager.
        
        Usage:
            async with session_manager.get_session() as db:
                # Use db for database operations
                pass
        """
        try:
            yield self.dynamodb_client
        except Exception as e:
            logger.error(f"Database session error: {e}")
            raise
        finally:
            # Cleanup if needed (DynamoDB doesn't require explicit cleanup)
            pass
    
    async def close_connections(self):
        """Close all database connections."""
        try:
            # DynamoDB client doesn't require explicit closing
            # but we can reset the instance for cleanup
            self._dynamodb_client = None
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")
    
    def reset(self):
        """Reset session manager (useful for testing)."""
        self._dynamodb_client = None
        logger.debug("SessionManager reset")


# Global session manager instance
session_manager = SessionManager()


# Convenience functions for common operations
async def get_db_session() -> AsyncGenerator[DynamoDBClient, None]:
    """Get database session - convenience function."""
    async with session_manager.get_session() as db:
        yield db


async def initialize_database() -> bool:
    """Initialize database - convenience function."""
    return await session_manager.initialize_database()


async def database_health_check() -> bool:
    """Database health check - convenience function."""
    return await session_manager.health_check()


# FastAPI dependency for database sessions
async def get_database() -> DynamoDBClient:
    """FastAPI dependency for getting database client."""
    return session_manager.dynamodb_client