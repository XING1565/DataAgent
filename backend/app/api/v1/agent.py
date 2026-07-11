from fastapi import APIRouter, Query

from app.schemas.agent import AgentEventsResponse, AgentStatus, AgentTraceResponse
from app.services.agent_event_store import AgentEventStore


router = APIRouter(prefix="/agent", tags=["agent"])
agent_event_store = AgentEventStore()


@router.get("/status", response_model=AgentStatus)
def get_agent_status(session_id: str | None = Query(default=None)) -> AgentStatus:
    return agent_event_store.get_status(session_id=session_id)


@router.get("/events", response_model=AgentEventsResponse)
def get_agent_events(
    session_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> AgentEventsResponse:
    return AgentEventsResponse(events=agent_event_store.get_events(session_id=session_id, limit=limit))


@router.get("/sessions/{session_id}/trace", response_model=AgentTraceResponse)
def get_agent_session_trace(session_id: str) -> AgentTraceResponse:
    return AgentTraceResponse(session_id=session_id, trace_steps=agent_event_store.get_latest_trace(session_id))
