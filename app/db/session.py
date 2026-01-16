"""
Database Session Management - 数据库会话管理
Provides database initialization and session context management.
"""

import os
from contextlib import contextmanager
from typing import Optional, Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from .models import Base


# Global engine and session factory
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def get_database_path() -> str:
    """Get the database file path from environment or default."""
    return os.environ.get("DATABASE_PATH", "payroll.db")


def init_database_simple(db_path: Optional[str] = None) -> Engine:
    """
    Initialize the database with a simple SQLite connection.
    简单初始化 - 使用标准 SQLite
    
    Args:
        db_path: Optional path to the database file
        
    Returns:
        SQLAlchemy Engine instance
    """
    global _engine, _SessionLocal
    
    if db_path is None:
        db_path = get_database_path()
    
    # Create SQLite engine
    database_url = f"sqlite:///{db_path}"
    
    _engine = create_engine(
        database_url,
        echo=os.environ.get("SQL_DEBUG", "").lower() == "true",
        connect_args={"check_same_thread": False},  # Allow multi-threaded access
    )
    
    # Enable foreign key support for SQLite
    @event.listens_for(_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    # Create session factory
    _SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=_engine
    )
    
    return _engine


def init_database_encrypted(db_path: Optional[str] = None, master_key: Optional[str] = None) -> Engine:
    """
    Initialize the database with SQLCipher encryption.
    加密初始化 - 使用 SQLCipher (如果可用)
    
    Args:
        db_path: Optional path to the database file
        master_key: Master key for database encryption
        
    Returns:
        SQLAlchemy Engine instance
    """
    global _engine, _SessionLocal
    
    if db_path is None:
        db_path = get_database_path()
    
    try:
        # Try to import sqlcipher3
        import sqlcipher3
        
        if master_key is None:
            master_key = os.environ.get("DB_MASTER_KEY", "")
        
        # Create SQLCipher engine
        database_url = f"sqlite+pysqlcipher://:{master_key}@/{db_path}"
        
        _engine = create_engine(
            database_url,
            echo=os.environ.get("SQL_DEBUG", "").lower() == "true",
        )
        
    except ImportError:
        # Fall back to standard SQLite
        print("Warning: SQLCipher not available, using standard SQLite")
        return init_database_simple(db_path)
    
    # Create session factory
    _SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=_engine
    )
    
    return _engine


def create_all_tables(engine: Optional[Engine] = None) -> None:
    """
    Create all database tables.
    创建所有数据库表
    
    Args:
        engine: Optional engine instance (uses global if not provided)
    """
    if engine is None:
        engine = get_engine()
    
    Base.metadata.create_all(bind=engine)


def drop_all_tables(engine: Optional[Engine] = None) -> None:
    """
    Drop all database tables (use with caution!).
    删除所有数据库表 - 谨慎使用！
    
    Args:
        engine: Optional engine instance (uses global if not provided)
    """
    if engine is None:
        engine = get_engine()
    
    Base.metadata.drop_all(bind=engine)


def get_engine() -> Engine:
    """
    Get the global database engine.
    
    Returns:
        SQLAlchemy Engine instance
        
    Raises:
        RuntimeError: If engine has not been initialized
    """
    global _engine
    
    if _engine is None:
        # Auto-initialize with defaults for convenience
        init_database_simple()
    
    return _engine


def get_session_factory() -> sessionmaker:
    """
    Get the session factory.
    
    Returns:
        SQLAlchemy sessionmaker instance
    """
    global _SessionLocal
    
    if _SessionLocal is None:
        get_engine()  # This will initialize the session factory
    
    return _SessionLocal


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Provide a transactional scope around a series of operations.
    提供事务性会话上下文管理器
    
    Usage:
        with session_scope() as session:
            session.query(User).all()
            session.add(new_user)
            # Automatically commits on success, rollbacks on exception
    
    Yields:
        SQLAlchemy Session instance
    """
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Session:
    """
    Get a new session instance.
    Note: Caller is responsible for closing the session.
    
    Returns:
        SQLAlchemy Session instance
    """
    session_factory = get_session_factory()
    return session_factory()


def close_engine() -> None:
    """
    Close the database engine and cleanup resources.
    关闭数据库引擎
    """
    global _engine, _SessionLocal
    
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionLocal = None
