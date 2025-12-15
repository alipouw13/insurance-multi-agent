"""Pydantic schema for per-agent execution response."""
from typing import Dict, List, Any, Optional
from pydantic import BaseModel


class AgentRunOut(BaseModel):
    success: bool = True
    agent_name: str
    claim_body: Dict[str, Any]
    conversation_chronological: List[Dict[str, str]]
    execution_id: Optional[str] = None
