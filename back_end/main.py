from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from DAL import ItemDAL
import os
import requests

MODEL_SERVICE_URL = os.getenv("MODEL_SERVICE_URL", "http://model-service:8001")

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

# Run with: uvicorn main:app --reload