"""
FastAPI application with workflow routes.

This is a minimal FastAPI app for testing workflow API endpoints.
In production, integrate workflows_router into your main FastAPI app.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.workflow_router import router as workflows_router
from .api.template_router import router as templates_router
from .agent_versioning.api.router import router as agents_router


def create_app() -> FastAPI:
    """
    Create FastAPI application with workflow routes.
    
    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="Cogitate Workflow API",
        description="LangGraph workflow orchestration API",
        version="1.0.0",
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include workflow routes
    app.include_router(workflows_router)
    
    # Include workflow template routes (stub)
    app.include_router(templates_router)
    
    # Include agent registry routes
    app.include_router(agents_router)
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "service": "cogitate-workflows",
            "version": "1.0.0"
        }
    
    # Register shutdown handler to close checkpointer and Langfuse
    @app.on_event("shutdown")
    async def shutdown_event():
        """Close checkpointer and Langfuse client on application shutdown."""
        from .checkpointing.config import CheckpointerManager
        from .observability import LangfuseManager
        
        # Close Langfuse first (flush traces)
        LangfuseManager.shutdown()
        
        # Then close checkpointer
        CheckpointerManager.close()
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.workflows.app:app",
        host="0.0.0.0",
        port=8000,  # Changed to match main app port for standalone testing
        reload=True,
    )
