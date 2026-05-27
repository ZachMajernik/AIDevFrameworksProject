from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from DAL import ItemDAL
from ollama import Client
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

# Run with: uvicorn main:app --reload