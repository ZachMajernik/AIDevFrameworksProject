import json
import os

from ollama import Client

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
DEMO_MODEL = os.getenv("AGENT_MODEL", "llama3.2")

_ollama = Client(host=OLLAMA_HOST)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string", "description": "City name."}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluate a basic arithmetic expression, e.g. '23 * 47'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Arithmetic expression."}
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_items",
            "description": "Search for items in the database by keyword.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Search keyword."}},
                "required": ["query"],
            },
        },
    },
]


def get_weather(city: str) -> dict:
    fake = {"san francisco": "62F and foggy", "denver": "78F and sunny"}
    return {"city": city, "forecast": fake.get(city.lower(), "75F and clear")}


def calculate(expression: str) -> dict:
    allowed = set("0123456789+-*/(). ")
    if not set(expression) <= allowed:
        raise ValueError("Only basic arithmetic is allowed.")
    return {"expression": expression, "result": eval(expression)}


def search_items(query: str) -> dict:
    catalog = ["Tyrannosaurus fossil", "Triceratops skull", "Python field guide"]
    hits = [name for name in catalog if query.lower() in name.lower()]
    return {"query": query, "matches": hits}


FUNCTIONS = {
    "get_weather": get_weather,
    "calculate": calculate,
    "search_items": search_items,
}


def run_function_calling_demo(user_message: str) -> dict:
    trace = []
    messages = [{"role": "user", "content": user_message}]
    trace.append({"step": "user_message", "content": user_message})

    first = _ollama.chat(model=DEMO_MODEL, messages=messages, tools=TOOLS)
    messages.append(
        {
            "role": "assistant",
            "content": first.message.content or "",
            "tool_calls": [
                {"function": {"name": tc.function.name, "arguments": dict(tc.function.arguments or {})}}
                for tc in (first.message.tool_calls or [])
            ],
        }
    )

    if not first.message.tool_calls:
        trace.append({"step": "model_response_no_tool", "content": first.message.content})
        return {"final_answer": first.message.content, "trace": trace}

    for tc in first.message.tool_calls:
        name = tc.function.name
        args = dict(tc.function.arguments or {})
        trace.append({"step": "model_decides_tool", "tool": name, "arguments": args})

        try:
            result = FUNCTIONS[name](**args)
        except Exception as exc:
            result = {"error": str(exc)}
        trace.append({"step": "tool_executed", "tool": name, "result": result})

        messages.append(
            {"role": "tool", "tool_name": name, "content": json.dumps(result, default=str)}
        )

    final = _ollama.chat(model=DEMO_MODEL, messages=messages, tools=TOOLS)
    trace.append({"step": "model_final_answer", "content": final.message.content})
    return {"final_answer": final.message.content, "trace": trace}


if __name__ == "__main__":
    for prompt in [
        "What is 23 * 47?",
        "Do we have any items about Python?",
    ]:
        print("=" * 70)
        print("USER:", prompt)
        out = run_function_calling_demo(prompt)
        for entry in out["trace"]:
            print(json.dumps(entry, indent=2, default=str))
        print("\nFINAL ANSWER:", out["final_answer"])
