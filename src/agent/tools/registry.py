"""Tool registry: build and manage tool sets per incarnation."""

from __future__ import annotations

from typing import Any, Callable

# Type alias for tool handler
ToolHandler = Callable[..., Any]


class ToolRegistry:
    """Registry of tools available in a given incarnation."""

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}  # name -> schema dict
        self._handlers: dict[str, ToolHandler] = {}  # name -> callable

    def register(self, schema: dict[str, Any], handler: ToolHandler) -> None:
        """Register a tool with its schema and handler."""
        name = schema["name"]
        self._tools[name] = schema
        self._handlers[name] = handler

    def get_schemas(self) -> list[dict[str, Any]]:
        """Return list of tool schemas for the Anthropic API."""
        return list(self._tools.values())

    def get_names(self) -> list[str]:
        """Return list of registered tool names."""
        return list(self._tools.keys())

    def execute(self, name: str, input_data: dict[str, Any], **ctx: Any) -> Any:
        """Execute a tool by name, passing context kwargs to the handler."""
        if name not in self._handlers:
            return {"error": f"Unknown tool: {name}"}
        try:
            return self._handlers[name](input_data, **ctx)
        except Exception as e:
            return {"error": f"Tool '{name}' raised an exception: {e}"}


def build_tool_registry(
    hook_type: str,
    agent_name: str,
    agent_config: Any,
    incarnation_state: dict[str, Any],
    api_url: str = "http://localhost:8000",
) -> ToolRegistry:
    """Build and return the tool registry for a given incarnation context."""
    from .core_tools import register_core_tools
    from .exec_tools import register_exec_tools
    from .process_tools import register_process_tools
    from .comms_tools import register_comms_tools
    from .agent_tools import register_agent_tools
    from .memory_tools import register_memory_tools

    registry = ToolRegistry()

    # Core tools always available
    register_core_tools(registry, agent_config, incarnation_state, api_url)

    # bash_exec: blocking commands; process_*: background/persistent processes
    register_exec_tools(registry, agent_config)
    register_process_tools(registry, agent_config, incarnation=incarnation_state.get("name", "unknown"))

    # Memory access tools (curated — no raw bash paths to samsara dirs needed)
    register_memory_tools(registry, agent_config)

    # Communication tools for most hooks
    if hook_type in ("human_message", "heartbeat", "scheduled_task", "agent_invite"):
        register_comms_tools(registry, agent_config, incarnation_state, api_url)

    # Agent-specific tools
    register_agent_tools(
        registry,
        agent_name,
        agent_config=agent_config,
        incarnation_state=incarnation_state,
        api_url=api_url,
    )

    return registry
