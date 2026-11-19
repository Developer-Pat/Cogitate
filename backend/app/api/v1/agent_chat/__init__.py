"""
Agent Chat API — JSON adapter for the cognitive pipeline.

Provides REST endpoints for agent-to-agent and script-to-agent communication
with structured JSON responses and full cognitive trace data.

Endpoints:
    POST   /api/v1/agent-chat/session          — Create session with cognitive config
    POST   /api/v1/agent-chat/message           — Send message, get JSON response + trace
    GET    /api/v1/agent-chat/session/{id}/trace — Get trace for session
    DELETE /api/v1/agent-chat/session/{id}      — Delete session
    GET    /api/v1/agent-chat/status            — External access status
    PUT    /api/v1/agent-chat/status            — Toggle external access
"""
