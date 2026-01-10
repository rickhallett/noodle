"""
MCP Server for Noodle.

Exposes noodle functionality as tools for Claude Code.
"""

import json
import sys
from datetime import datetime, timezone

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import noodle modules
from noodle.config import ensure_dirs, get_inbox_path
from noodle.db import Database
from noodle.ingress import append_to_inbox
from noodle.surfacing import (
    generate_daily_digest,
    generate_weekly_review,
    get_entries_formatted,
    search_entries_formatted,
)

# Create MCP server
server = Server("noodle")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="noodle_add",
            description="Capture a thought to the noodle inbox. Use this to save ideas, tasks, notes, or anything worth remembering.",
            inputSchema={
                "type": "object",
                "properties": {
                    "thought": {
                        "type": "string",
                        "description": "The thought to capture",
                    },
                },
                "required": ["thought"],
            },
        ),
        Tool(
            name="noodle_search",
            description="Search noodle entries using full-text search. Returns matching entries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default: 10)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="noodle_tasks",
            description="List tasks from noodle, optionally filtered by project.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Filter by project slug (optional)",
                    },
                    "include_completed": {
                        "type": "boolean",
                        "description": "Include completed tasks (default: false)",
                        "default": False,
                    },
                },
            },
        ),
        Tool(
            name="noodle_complete",
            description="Mark a task as completed in noodle.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {
                        "type": "string",
                        "description": "The ID of the task to complete",
                    },
                },
                "required": ["entry_id"],
            },
        ),
        Tool(
            name="noodle_digest",
            description="Get the daily digest showing due tasks and recent entries.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="noodle_weekly",
            description="Get the weekly review showing stats and progress.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="noodle_pending",
            description="Get entries that need manual review (low confidence classifications).",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="noodle_retype",
            description="Change the type of an entry (task, thought, person, or event).",
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_id": {
                        "type": "string",
                        "description": "The ID of the entry to retype",
                    },
                    "new_type": {
                        "type": "string",
                        "description": "New type: task, thought, person, or event",
                        "enum": ["task", "thought", "person", "event"],
                    },
                },
                "required": ["entry_id", "new_type"],
            },
        ),
        Tool(
            name="noodle_context",
            description="Get entries related to a topic for context. Useful when working on something and need background info.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic to find related entries for",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default: 5)",
                        "default": 5,
                    },
                },
                "required": ["topic"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "noodle_add":
            return await tool_add(arguments)
        elif name == "noodle_search":
            return await tool_search(arguments)
        elif name == "noodle_tasks":
            return await tool_tasks(arguments)
        elif name == "noodle_complete":
            return await tool_complete(arguments)
        elif name == "noodle_digest":
            return await tool_digest(arguments)
        elif name == "noodle_weekly":
            return await tool_weekly(arguments)
        elif name == "noodle_pending":
            return await tool_pending(arguments)
        elif name == "noodle_retype":
            return await tool_retype(arguments)
        elif name == "noodle_context":
            return await tool_context(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def tool_add(args: dict) -> list[TextContent]:
    """Capture a thought."""
    thought = args.get("thought", "").strip()
    if not thought:
        return [TextContent(type="text", text="Error: Empty thought")]

    ensure_dirs()
    inbox_path = get_inbox_path()
    entry_id = append_to_inbox(thought, inbox_path)

    return [TextContent(type="text", text=f"Captured: {entry_id}")]


async def tool_search(args: dict) -> list[TextContent]:
    """Search entries."""
    query = args.get("query", "").strip()
    limit = args.get("limit", 10)

    if not query:
        return [TextContent(type="text", text="Error: Empty query")]

    result = search_entries_formatted(query, limit=limit)
    return [TextContent(type="text", text=result)]


async def tool_tasks(args: dict) -> list[TextContent]:
    """List tasks."""
    project = args.get("project")
    include_completed = args.get("include_completed", False)

    result = get_entries_formatted(
        entry_type="task",
        project=project,
        include_completed=include_completed,
    )
    return [TextContent(type="text", text=result)]


async def tool_complete(args: dict) -> list[TextContent]:
    """Complete a task."""
    entry_id = args.get("entry_id", "").strip()
    if not entry_id:
        return [TextContent(type="text", text="Error: No entry_id provided")]

    db = Database()
    success = db.complete_task(entry_id)

    if success:
        return [TextContent(type="text", text=f"Completed: {entry_id}")]
    else:
        return [TextContent(type="text", text=f"Not found or not a task: {entry_id}")]


async def tool_digest(args: dict) -> list[TextContent]:
    """Get daily digest."""
    digest = generate_daily_digest()
    return [TextContent(type="text", text=digest)]


async def tool_weekly(args: dict) -> list[TextContent]:
    """Get weekly review."""
    review = generate_weekly_review()
    return [TextContent(type="text", text=review)]


async def tool_pending(args: dict) -> list[TextContent]:
    """Get pending review entries."""
    db = Database()
    entries = db.get_pending_reclassification()

    if not entries:
        return [TextContent(type="text", text="No entries pending review.")]

    lines = ["Entries pending manual review:", ""]
    for entry in entries:
        lines.append(f"  {entry['id']}  {entry['type']:8}  {entry['title'][:50]}")

    return [TextContent(type="text", text="\n".join(lines))]


async def tool_retype(args: dict) -> list[TextContent]:
    """Change entry type."""
    entry_id = args.get("entry_id", "").strip()
    new_type = args.get("new_type", "").strip()

    if not entry_id:
        return [TextContent(type="text", text="Error: No entry_id provided")]
    if new_type not in ("task", "thought", "person", "event"):
        return [TextContent(type="text", text=f"Error: Invalid type '{new_type}'")]

    db = Database()
    success = db.update_entry_type(entry_id, new_type)

    if success:
        return [TextContent(type="text", text=f"Retyped {entry_id} → {new_type}")]
    else:
        return [TextContent(type="text", text=f"Entry not found: {entry_id}")]


async def tool_context(args: dict) -> list[TextContent]:
    """Get context entries for a topic."""
    topic = args.get("topic", "").strip()
    limit = args.get("limit", 5)

    if not topic:
        return [TextContent(type="text", text="Error: No topic provided")]

    # Use full-text search for context
    result = search_entries_formatted(topic, limit=limit)

    if result.startswith("No entries"):
        return [TextContent(type="text", text=f"No context found for '{topic}'")]

    return [TextContent(type="text", text=f"Context for '{topic}':\n\n{result}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
