import json
import os
import re

import requests
from ollama import Client

SELF_API_URL = os.getenv("SELF_API_URL", "http://localhost:8000")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
AGENT_MODEL = os.getenv("AGENT_MODEL", "llama3.2")

DEFAULT_MAX_STEPS = 8

DESTRUCTIVE_TOOLS = {"create_item"}

_ollama = Client(host=OLLAMA_HOST)


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_items",
            "description": (
                "Search the item catalog in the database by keyword. Returns a "
                "list of matching items (each with id, name, description). Use "
                "this to find out whether items about a topic already exist."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keyword or phrase to search item names and descriptions for.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_item",
            "description": (
                "Create a new item in the catalog. This WRITES to the database, "
                "so it requires user confirmation before it runs. Only call this "
                "AFTER a search has confirmed the item does not already exist, or "
                "when the user explicitly asks to add an item."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Short name/title of the item."},
                    "description": {
                        "type": "string",
                        "description": "A meaningful one-sentence description of the item. Required, never leave blank.",
                    },
                },
                "required": ["name", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_knowledge_base",
            "description": (
                "Ask the paleontology/dinosaur knowledge base (the RAG system). "
                "It retrieves relevant catalog items and answers the question "
                "grounded in them. Use this for factual questions or summaries."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "A natural-language question to answer from the knowledge base.",
                    }
                },
                "required": ["question"],
            },
        },
    },
]


def _tool_search_items(query: str):
    resp = requests.get(f"{SELF_API_URL}/items", timeout=20)
    resp.raise_for_status()
    items = resp.json()
    q = (query or "").lower().strip()
    if not q:
        return items
    matches = [
        it
        for it in items
        if q in (it.get("name") or "").lower()
        or q in (it.get("description") or "").lower()
    ]
    return {"query": query, "count": len(matches), "items": matches}


def _tool_create_item(name: str, description: str = ""):
    resp = requests.post(
        f"{SELF_API_URL}/new-item",
        json={"name": name, "description": description},
        timeout=20,
    )
    resp.raise_for_status()
    return {"created": resp.json()}


def _tool_ask_knowledge_base(question: str):
    resp = requests.post(
        f"{SELF_API_URL}/ask",
        json={"question": question},
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()


TOOL_IMPLEMENTATIONS = {
    "search_items": _tool_search_items,
    "create_item": _tool_create_item,
    "ask_knowledge_base": _tool_ask_knowledge_base,
}


SYSTEM_PROMPT = (
    "You are an autonomous assistant for an item-catalog application with three "
    "tools: search_items, create_item, and ask_knowledge_base. 'Items' always "
    "means rows in this application's database, NOT general knowledge.\n\n"
    "RULES:\n"
    "1. You MUST use tools to inspect or change the catalog. Never answer a task "
    "about items from your own knowledge, and never reply with prose before you "
    "have used the tools. If a task mentions finding or creating items, your "
    "FIRST action must be a search_items call.\n"
    "2. Always use real tool calls. Never write a tool call as plain text.\n"
    "3. Tool arguments are plain values, not schemas. search_items example: "
    "{\"query\": \"Triceratops\"}.\n"
    "4. For a conditional task such as 'find items about X, and if there aren't "
    "any create one', respond with BOTH a search_items call for X AND a "
    "create_item call for X in the same turn. The system runs the search first "
    "and AUTOMATICALLY skips the creation if matching items already exist, so it "
    "is always safe to include both.\n"
    "5. Every create_item call MUST include a 'name' and a meaningful one-sentence "
    "'description'. Never leave the description blank.\n"
    "6. Only after the tools have done the work, reply with a short plain-text "
    "summary of what you did."
)


_STRING_PARAMS = {
    "search_items": ["query"],
    "create_item": ["name", "description"],
    "ask_knowledge_base": ["question"],
}


def _sanitize_arguments(name: str, arguments: dict) -> dict:
    arguments = dict(arguments or {})
    expected = _STRING_PARAMS.get(name)
    if not expected:
        return arguments

    schema_noise = {"string", "str", "object"}

    def usable(v):
        return isinstance(v, str) and v.strip() and v.strip() not in schema_noise

    clean = {}
    used = set()
    for param in expected:
        val = arguments.get(param)
        if usable(val):
            clean[param] = val.strip()
            used.add(val.strip())

    recovered = [
        v.strip()
        for v in arguments.values()
        if usable(v) and v.strip() not in used
    ]
    for param in expected:
        if param not in clean and recovered:
            clean[param] = recovered.pop(0)

    return clean


def _parse_text_tool_call(content: str):
    if not content:
        return None
    for match in re.findall(r"\{.*\}", content, re.DOTALL):
        try:
            obj = json.loads(match)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        name = obj.get("name")
        if name in TOOL_IMPLEMENTATIONS:
            args = obj.get("parameters") or obj.get("arguments") or obj.get("input") or {}
            if isinstance(args, dict):
                return {"name": name, "arguments": args}
    return None


def _execute_tool(name: str, arguments: dict):
    func = TOOL_IMPLEMENTATIONS.get(name)
    if func is None:
        return None, f"Unknown tool '{name}'."
    try:
        return func(**(arguments or {})), None
    except requests.exceptions.HTTPError as exc:
        return None, f"Tool '{name}' API returned an error: {exc.response.status_code} {exc.response.text}"
    except requests.exceptions.RequestException as exc:
        return None, f"Tool '{name}' could not reach the API: {exc}"
    except TypeError as exc:
        return None, f"Tool '{name}' was called with bad arguments: {exc}"
    except Exception as exc:
        return None, f"Tool '{name}' failed: {exc}"


def _append_tool_result(messages, steps, name, arguments, output, error):
    content = error if error is not None else json.dumps(output, default=str)
    messages.append({"role": "tool", "tool_name": name, "content": content})
    steps.append(
        {
            "type": "tool_call",
            "tool": name,
            "input": arguments,
            "output": (error if error is not None else output),
            "error": error is not None,
        }
    )


def _limit_reached(steps, messages):
    return {
        "status": "complete",
        "result": (
            "Step limit reached before the task was finished. "
            "Here is the reasoning trace of what was attempted."
        ),
        "steps": steps,
        "messages": messages,
        "queue": [],
        "pending": None,
    }


def run_agent(task=None, messages=None, steps=None, queue=None,
              decision=None, max_steps=DEFAULT_MAX_STEPS):
    messages = list(messages) if messages else []
    steps = list(steps) if steps else []
    queue = list(queue) if queue else []

    if task is not None and not messages:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ]

    tool_steps_taken = sum(1 for s in steps if s.get("type") == "tool_call")

    if decision is not None and queue:
        call = queue[0]
        name = call["name"]
        arguments = call.get("arguments", {})
        if decision == "approved":
            output, error = _execute_tool(name, arguments)
            _append_tool_result(messages, steps, name, arguments, output, error)
            tool_steps_taken += 1
        else:
            denial = "User denied permission to run this action. Do not retry it."
            messages.append({"role": "tool", "tool_name": name, "content": denial})
            steps.append(
                {
                    "type": "tool_call",
                    "tool": name,
                    "input": arguments,
                    "output": "Denied by user.",
                    "error": True,
                    "denied": True,
                }
            )
        queue = queue[1:]

    while True:
        found_existing = False
        last_search_query = None
        while queue:
            if tool_steps_taken >= max_steps:
                return _limit_reached(steps, messages)

            call = queue[0]
            name = call["name"]
            arguments = call.get("arguments", {})

            if name in DESTRUCTIVE_TOOLS:
                if found_existing:
                    note = "Skipped: matching items already exist, so no new item was created."
                    messages.append({"role": "tool", "tool_name": name, "content": note})
                    steps.append(
                        {
                            "type": "tool_call",
                            "tool": name,
                            "input": arguments,
                            "output": "Skipped — matching items already exist.",
                            "error": False,
                            "skipped": True,
                        }
                    )
                    tool_steps_taken += 1
                    queue = queue[1:]
                    continue

                if name == "create_item":
                    arguments = dict(arguments)
                    if not arguments.get("name"):
                        arguments["name"] = last_search_query or "New item"
                    if not arguments.get("description"):
                        arguments["description"] = f"An item related to {arguments['name']}."
                    queue[0] = {"name": name, "arguments": arguments}

                steps.append(
                    {"type": "awaiting_confirmation", "tool": name, "input": arguments}
                )
                return {
                    "status": "needs_confirmation",
                    "result": None,
                    "steps": steps,
                    "messages": messages,
                    "queue": queue,
                    "pending": {"tool": name, "input": arguments},
                }

            output, error = _execute_tool(name, arguments)
            _append_tool_result(messages, steps, name, arguments, output, error)
            if name == "search_items":
                last_search_query = arguments.get("query") or last_search_query
                if isinstance(output, dict) and output.get("count", 0) > 0:
                    found_existing = True
            tool_steps_taken += 1
            queue = queue[1:]

        if tool_steps_taken >= max_steps:
            return _limit_reached(steps, messages)

        try:
            response = _ollama.chat(
                model=AGENT_MODEL,
                messages=messages,
                tools=TOOL_SCHEMAS,
                options={"temperature": 0.2},
            )
        except Exception as exc:
            return {
                "status": "error",
                "result": f"The agent's model call failed: {exc}",
                "steps": steps,
                "messages": messages,
                "queue": [],
                "pending": None,
            }

        msg = response.message
        tool_calls = getattr(msg, "tool_calls", None)

        if tool_calls:
            normalized = [
                {"name": tc.function.name,
                 "arguments": _sanitize_arguments(tc.function.name, tc.function.arguments or {})}
                for tc in tool_calls
            ]
        else:
            parsed = _parse_text_tool_call(msg.content)
            if parsed is None:
                messages.append({"role": "assistant", "content": msg.content or ""})
                if msg.content:
                    steps.append({"type": "final", "content": msg.content})
                return {
                    "status": "complete",
                    "result": msg.content or "(no answer)",
                    "steps": steps,
                    "messages": messages,
                    "queue": [],
                    "pending": None,
                }
            normalized = [
                {"name": parsed["name"],
                 "arguments": _sanitize_arguments(parsed["name"], parsed["arguments"])}
            ]

        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"function": {"name": c["name"], "arguments": c["arguments"]}}
                    for c in normalized
                ],
            }
        )
        queue = normalized
