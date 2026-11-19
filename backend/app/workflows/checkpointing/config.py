"""
Checkpointing configuration for LangGraph workflows.

Provides factory methods for creating appropriate checkpointers
based on environment (development vs production).

IMPORTANT: LangGraph 1.0+ Checkpointer Lifecycle
=================================================

In LangGraph 1.0+, `SqliteSaver.from_conn_string()` returns a **context manager**,
not a direct instance. This is a BREAKING CHANGE from earlier versions.

OLD (LangGraph <1.0):
    checkpointer = SqliteSaver.from_conn_string("./db.sqlite")
    # Returns: SqliteSaver instance
    graph.compile(checkpointer=checkpointer)

NEW (LangGraph 1.0+):
    ctx = SqliteSaver.from_conn_string("./db.sqlite")
    # Returns: _GeneratorContextManager
    checkpointer = ctx.__enter__()  # Must enter context to get instance
    graph.compile(checkpointer=checkpointer)
    # Later: ctx.__exit__(None, None, None)  # Must close on shutdown

CRITICAL:
- You MUST call __enter__() to get the actual SqliteSaver instance
- You MUST call __exit__() on application shutdown to close DB connection
- Using the context manager directly in graph.compile() will fail
- Background tasks need the checkpointer to stay open

Usage:
    ```python
    # Development - singleton manager handles lifecycle
    from app.workflows.checkpointing.config import CheckpointerManager
    
    checkpointer = CheckpointerManager.get_checkpointer()
    graph.compile(checkpointer=checkpointer)
    
    # On shutdown:
    CheckpointerManager.close()
    
    # Production - use Postgres with proper async lifecycle
    os.environ["ENVIRONMENT"] = "production"
    os.environ["WORKFLOW_DB_URL"] = "postgresql://..."
    checkpointer = CheckpointerManager.get_checkpointer()
    ```
"""

from langgraph.checkpoint.sqlite import SqliteSaver
from pathlib import Path
import os
import atexit

from app.core.config import Paths, get_settings


class CheckpointerManager:
    """
    Singleton manager for checkpointer lifecycle.
    
    Creates and maintains a single checkpointer instance
    for the application lifetime.
    
    Handles LangGraph 1.0+ context manager API by:
    1. Calling __enter__() to get the actual instance
    2. Registering __exit__() for application shutdown
    3. Keeping the checkpointer open for background tasks
    
    Attributes:
        _checkpointer: The actual SqliteSaver instance (after __enter__)
        _context_manager: The context manager (for calling __exit__ later)
        _db_path: Path to the database file
    
    Usage:
        ```python
        # Get checkpointer instance (automatically opens if needed)
        checkpointer = CheckpointerManager.get_checkpointer()
        
        # Use in graph compilation
        graph = StateGraph(WorkflowState)
        compiled = graph.compile(checkpointer=checkpointer)
        
        # On application shutdown (automatic via atexit)
        CheckpointerManager.close()
        ```
    
    Example with FastAPI:
        ```python
        from fastapi import FastAPI
        from app.workflows.checkpointing.config import CheckpointerManager
        
        app = FastAPI()
        
        @app.on_event("shutdown")
        async def shutdown_event():
            CheckpointerManager.close()
        ```
    """
    
    _checkpointer = None
    _context_manager = None
    _db_path = None
    
    @classmethod
    def get_checkpointer(cls, db_path: str | None = None):
        """
        Get or create checkpointer instance.
        
        Returns the same instance on repeated calls.
        Creates a new instance only if db_path changes.
        
        IMPORTANT: This method calls __enter__() on the context manager
        to get the actual SqliteSaver instance. The instance stays open
        until close() is called.
        
        Args:
            db_path: Optional path to SQLite database file.
                    If None, uses environment variable or default.
        
        Returns:
            SqliteSaver instance for checkpointing (already opened)
            
        Raises:
            ValueError: If production environment without WORKFLOW_DB_URL
            
        Environment Variables:
            ENVIRONMENT: 'development' or 'production' (default: 'development')
            WORKFLOW_CHECKPOINT_DB: Path to SQLite DB
                (default: <project root>/checkpoints.db)
            WORKFLOW_DB_URL: Postgres connection string (production only)
        
        Example:
            ```python
            # First call - creates and opens checkpointer
            cp1 = CheckpointerManager.get_checkpointer()
            
            # Second call - returns same instance
            cp2 = CheckpointerManager.get_checkpointer()
            
            # cp1 is cp2  # True - same instance
            ```
        """
        # Use default path if not provided
        if db_path is None:
            # The default is ROOTED, not cwd-relative. "./checkpoints.db"
            # resolved against whatever directory the process was started in, so
            # the workflow journal landed somewhere different depending on how the
            # app was launched - and a second copy silently appeared at each new
            # cwd. The Paths locator already owns the root the rest of the app
            # uses; this now agrees with it.
            db_path = os.getenv(
                "WORKFLOW_CHECKPOINT_DB",
                str(Paths.from_settings(get_settings()).root / "checkpoints.db"),
            )
        
        # Create new checkpointer if path changed or not created yet
        if cls._checkpointer is None or cls._db_path != db_path:
            # Close existing if any
            if cls._checkpointer is not None:
                cls.close()
            
            # Ensure directory exists
            db_file = Path(db_path)
            db_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Get the context manager (LangGraph 1.0+ API)
            ctx_manager = SqliteSaver.from_conn_string(str(db_path))
            
            # Enter the context to get the actual SqliteSaver instance
            # This is the CRITICAL step for LangGraph 1.0+ compatibility
            try:
                checkpointer_instance = ctx_manager.__enter__()
            except Exception as e:
                raise RuntimeError(
                    f"Failed to open SqliteSaver context: {e}. "
                    "This is a LangGraph 1.0+ lifecycle issue. "
                    "Make sure to call __enter__() on the context manager."
                ) from e
            
            # Store both the instance and the context manager
            cls._checkpointer = checkpointer_instance
            cls._context_manager = ctx_manager
            cls._db_path = db_path
            
            # Register cleanup on application exit
            if not cls._atexit_registered:
                atexit.register(cls.close)
                cls._atexit_registered = True
        
        return cls._checkpointer
    
    @classmethod
    def close(cls):
        """
        Close checkpointer and cleanup resources.
        
        IMPORTANT: Must be called on application shutdown to:
        1. Close database connections
        2. Flush pending writes
        3. Release file locks
        
        This is automatically registered via atexit, but can be
        called manually for testing or explicit cleanup.
        
        Example:
            ```python
            # Manual cleanup (e.g., in tests)
            CheckpointerManager.close()
            
            # Or in FastAPI shutdown event
            @app.on_event("shutdown")
            async def shutdown():
                CheckpointerManager.close()
            ```
        """
        if cls._context_manager is not None:
            try:
                # Exit the context to close database
                cls._context_manager.__exit__(None, None, None)
            except Exception as e:
                # Log but don't raise - this is cleanup
                print(f"Warning: Error closing checkpointer: {e}")
            finally:
                cls._checkpointer = None
                cls._context_manager = None
                cls._db_path = None
    
    _atexit_registered = False
    
    @classmethod
    def reset(cls):
        """
        Reset manager state (for testing only).
        
        WARNING: Only use in tests. This will close the checkpointer
        and allow creating a new one with a different path.
        
        Example:
            ```python
            # In test cleanup
            def teardown_method():
                CheckpointerManager.reset()
            ```
        """
        cls.close()
        cls._atexit_registered = False


# For backwards compatibility, alias the manager
CheckpointerConfig = CheckpointerManager
