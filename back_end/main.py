from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from DAL import ItemDAL

#copilot implemented the model architecture so that the trained model can be used
import torch
import torch.nn as nn
import numpy as np
import joblib
from pathlib import Path

# ── Model architecture (must match model_training.ipynb) ─────────────────────
class SimpleClassifier(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, num_classes: int):
        super().__init__()
        self.layer1 = nn.Linear(input_size, hidden_size)
        self.relu   = nn.ReLU()
        self.layer2 = nn.Linear(hidden_size, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.relu(self.layer1(x))
        x = self.layer2(x)
        return x

# ── Load model + scaler once at startup (not per-request) ────────────────────
_BASE = Path(__file__).parent
IRIS_CLASSES = ["setosa", "versicolor", "virginica"]

_scaler = joblib.load(_BASE / "scaler.pkl")

_classifier = SimpleClassifier(input_size=4, hidden_size=16, num_classes=3)
_classifier.load_state_dict(torch.load(_BASE / "model.pth", map_location="cpu"))
_classifier.eval()

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
    if len(req.features) != 4:
        raise HTTPException(status_code=422, detail="Expected exactly 4 features: [sepal_length, sepal_width, petal_length, petal_width]")

    arr = np.array(req.features, dtype=np.float32).reshape(1, -1)
    arr = _scaler.transform(arr).astype(np.float32)

    with torch.no_grad():
        logits     = _classifier(torch.from_numpy(arr))
        probs      = torch.softmax(logits, dim=1).squeeze()
        class_idx  = int(probs.argmax().item())
        confidence = round(float(probs[class_idx].item()), 4)

    return {"prediction": IRIS_CLASSES[class_idx], "confidence": confidence}

# Run with: uvicorn main:app --reload