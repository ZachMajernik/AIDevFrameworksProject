from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from DAL import ItemDAL
from ollama import Client
import json
import os
import requests

MODEL_SERVICE_URL = os.getenv("MODEL_SERVICE_URL", "http://model-service:8001")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
ollama_client = Client(host=OLLAMA_HOST)

app = FastAPI()
dal = ItemDAL()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Item(BaseModel):
    name: str
    description: Optional[str]

class PredictionRequest(BaseModel):
    features: list[float]

class ChatRequest(BaseModel):
    message: str
    conversation_history: list = []

class ChatResponse(BaseModel):
    reply: str
    conversation_history: list

class AnalyzeRequest(BaseModel):
    content: str

# Your endpoints here
@app.get("/items", status_code=200) #ChatGPT said to add the status codes here so that if there is no error, this is the default status code if it worked
async def get_items():
    return await dal.get_all_items()

@app.get("/item/{id}", status_code=200)
async def get_item_by_id(id: str):
    item = await dal.get_item_by_id(id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@app.post("/new-item", status_code=201)
async def new_item(item: Item):
    return await dal.create_item(item.name, item.description)

@app.put("/update-item/{id}", status_code=200)
async def update_item(id: str, item: Item):
    updated = await dal.update_item(id, item.name, item.description)
    if updated is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return updated

@app.delete("/delete-item/{id}", status_code=204)
async def delete_item(id: str):
    deleted = await dal.delete_item(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    
@app.post("/predict")
def predict(req: PredictionRequest):
    try:
        resp = requests.post(
            f"{MODEL_SERVICE_URL}/predict",
            json={"features": req.features},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="Model service unavailable")
    except requests.exceptions.HTTPError:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert paleontologist specializing in dinosaurs. "
                "You only answer questions related to paleontology, dinosaurs, and prehistoric life. DO NOT ANSWER QUESTIONS ABOUT ANY OTHER TOPIC. "
                "If a question is unrelated to these topics, politely decline with \"I'm sorry, But I can only answer questions about paleontology and dinosaurs.\""
            )
        }
    ]
    messages.extend(request.conversation_history)
    messages.append({"role": "user", "content": request.message})

    try:
        response = ollama_client.chat(
            model="llama3.2",
            messages=messages,
            options={
                "temperature": 0.5,
                "num_predict": 512
            }
        )
        reply = response.message.content

        updated_history = request.conversation_history + [
            {"role": "user", "content": request.message},
            {"role": "assistant", "content": reply}
        ]
        return ChatResponse(reply=reply, conversation_history=updated_history)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Copilot helped make this enpoint with the functionality to strip and check json data and reprompt Ollama if necessary
# It also came up with the system prompt and the few shot example
@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    system_prompt = """You are a data extraction assistant for an item catalog application.
                        Analyze the provided item description and respond with ONLY valid JSON in this exact format:
                        {
                        "name": "item name",
                        "categories": ["category1", "category2"],
                        "tags": ["tag1", "tag2", "tag3"],
                        "description": "one sentence summary"
                        }
                        Do not include any text, explanation, or markdown outside the JSON object."""

    few_shot = """Example:
                    Input: "Vintage wooden bookshelf with five shelves and a dark walnut finish. Some minor scratches but sturdy and holds a lot of books."
                    Output: {"name": "Vintage wooden bookshelf", "categories": ["furniture", "storage"], "tags": ["wooden", "vintage", "bookshelf", "walnut"], "description": "A sturdy vintage walnut bookshelf with minor cosmetic wear but good storage capacity."}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": few_shot + "\n\nNow analyze this:\n" + request.content}
    ]

    def call_ollama():
        return ollama_client.chat(
            model="llama3.2",
            messages=messages,
            options={"temperature": 0.2, "num_predict": 512}
        )

    try:
        response = call_ollama()
        raw = response.message.content

        # Strip markdown code fences if the model wraps the JSON
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)

        required = ["name", "categories", "tags", "description"]
        for field in required:
            if field not in result:
                raise ValueError(f"Missing field: {field}")

        return result

    except (json.JSONDecodeError, ValueError):
        # Retry once with an explicit reminder
        messages.append({"role": "user", "content": "Your response was not valid JSON. Reply with ONLY the JSON object, no other text."})
        try:
            response = call_ollama()
            raw = response.message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            result = json.loads(raw.strip())
            required = ["name", "categories", "tags", "description"]
            for field in required:
                if field not in result:
                    raise ValueError(f"Missing field: {field}")
            return result
        except Exception:
            raise HTTPException(status_code=422, detail="LLM returned invalid JSON after retry. Please try again.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Run with: uvicorn main:app --reload