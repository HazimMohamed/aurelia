"""Shared return types for the Aurelia runtime and Manas layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class IncarnationSummary:
    name: str
    agent: str
    status: str          # "primary" | "active" | "dissolved"
    cycle: int
    last_active: Optional[str] = None


@dataclass
class AgentResponse:
    agent: str
    incarnation: str
    cycle: int
    content: str


@dataclass
class TranscriptEntry:
    ts: str
    type: str
    content: Optional[str] = None
    cycle: Optional[int] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentSummary:
    name: str
    status: str
    incarnation: Optional[str] = None
    cycle: Optional[int] = None
    last_active: Optional[str] = None
    budget_remaining: Optional[int] = None
    weekly_budget: Optional[int] = None
    scheduler_queue: int = 0


@dataclass
class HealthReport:
    status: str
    agents: list[AgentSummary]
    pending_dashboard: int = 0
