"""
Nexus Agent OS — MCP Registry Server
Tools: register_agent, list_agents, ping_agent, kill_agent,
       restart_agent, run_task, get_agent_code

The meta-agents call these tools to manage the registry.
Run standalone: python mcp_server.py
"""
import asyncio
import json
from pathlib import Path

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

import registry as reg

server = Server("nexus-registry")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="register_agent",
            description="Register a new agent in the Nexus registry",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string"},
                    "record":   {"type": "string", "description": "JSON string of agent record"},
                },
                "required": ["agent_id", "record"],
            },
        ),
        types.Tool(
            name="list_agents",
            description="List all agents currently in the Nexus registry",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_agent",
            description="Get details of a specific agent by ID",
            inputSchema={
                "type": "object",
                "properties": {"agent_id": {"type": "string"}},
                "required": ["agent_id"],
            },
        ),
        types.Tool(
            name="ping_agent",
            description="Health-check a running agent subprocess",
            inputSchema={
                "type": "object",
                "properties": {"agent_id": {"type": "string"}},
                "required": ["agent_id"],
            },
        ),
        types.Tool(
            name="restart_agent",
            description="Kill and restart a deployed agent subprocess",
            inputSchema={
                "type": "object",
                "properties": {"agent_id": {"type": "string"}},
                "required": ["agent_id"],
            },
        ),
        types.Tool(
            name="kill_agent",
            description="Gracefully stop a running agent subprocess",
            inputSchema={
                "type": "object",
                "properties": {"agent_id": {"type": "string"}},
                "required": ["agent_id"],
            },
        ),
        types.Tool(
            name="run_task",
            description="Send a task to a deployed agent and get its output",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string"},
                    "task":     {"type": "string"},
                },
                "required": ["agent_id", "task"],
            },
        ),
        types.Tool(
            name="get_agent_code",
            description="Read the generated source code of a deployed agent",
            inputSchema={
                "type": "object",
                "properties": {"agent_id": {"type": "string"}},
                "required": ["agent_id"],
            },
        ),
        types.Tool(
            name="deregister_agent",
            description="Remove an agent from the registry permanently",
            inputSchema={
                "type": "object",
                "properties": {"agent_id": {"type": "string"}},
                "required": ["agent_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    def _resp(data) -> list[types.TextContent]:
        return [types.TextContent(type="text", text=json.dumps(data, indent=2))]

    if name == "register_agent":
        record = json.loads(arguments.get("record", "{}"))
        result = reg.register_agent(arguments["agent_id"], record)
        return _resp({"registered": True, "agent_id": result["agent_id"]})

    elif name == "list_agents":
        agents = reg.list_agents()
        return _resp({
            "count": len(agents),
            "agents": [
                {
                    "agent_id":   a["agent_id"],
                    "agent_name": a.get("agent_name", ""),
                    "status":     a.get("status", ""),
                    "health":     a.get("health_status", ""),
                    "task_count": a.get("task_count", 0),
                }
                for a in agents
            ],
        })

    elif name == "get_agent":
        agent = reg.get_agent(arguments["agent_id"])
        return _resp(agent or {"error": "Not found"})

    elif name == "ping_agent":
        result = reg.ping_agent(arguments["agent_id"])
        return _resp(result)

    elif name == "restart_agent":
        new_pid = reg.restart_agent(arguments["agent_id"])
        return _resp({"restarted": True, "new_pid": new_pid})

    elif name == "kill_agent":
        ok = reg.stop_agent(arguments["agent_id"])
        return _resp({"stopped": ok})

    elif name == "run_task":
        result = reg.run_task_on_agent(arguments["agent_id"], arguments["task"])
        return _resp(result)

    elif name == "get_agent_code":
        agent = reg.get_agent(arguments["agent_id"])
        if not agent:
            return _resp({"error": "Agent not found"})
        code_path = Path(agent.get("code_path", ""))
        agent_py = code_path / "agent.py"
        if agent_py.exists():
            return _resp({"agent_id": arguments["agent_id"], "code": agent_py.read_text()})
        return _resp({"error": "agent.py not found"})

    elif name == "deregister_agent":
        reg.stop_agent(arguments["agent_id"])
        ok = reg.deregister_agent(arguments["agent_id"])
        return _resp({"deregistered": ok})

    return _resp({"error": f"Unknown tool: {name}"})


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())