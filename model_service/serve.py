from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
import torch.nn as nn
import numpy as np
import joblib
from pathlib import Path

_BASE = Path(__file__).parent

IRIS_CLASSES = ["setosa", "versicolor", "virginica"]

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

_scaler = joblib.load(_BASE / "scaler.pkl")

_classifier = SimpleClassifier(input_size=4, hidden_size=16, num_classes=3)
_classifier.load_state_dict(torch.load(_BASE / "model.pth", map_location="cpu"))
_classifier.eval()

app = FastAPI()

class PredictionRequest(BaseModel):
    features: list[float]

@app.get("/health")
def health():
    return {"status": "healthy", "model_loaded": True}

@app.post("/predict")
def predict(req: PredictionRequest):
    if len(req.features) != 4:
        raise HTTPException(status_code=422, detail="Expected exactly 4 features: [sepal_length, sepal_width, petal_length, petal_width]")

    arr = np.array(req.features, dtype=np.float32).reshape(1, -1)
    arr = _scaler.transform(arr).astype(np.float32)

    with torch.no_grad():
        logits    = _classifier(torch.from_numpy(arr))
        probs     = torch.softmax(logits, dim=1).squeeze()
        class_idx = int(probs.argmax().item())
        confidence = round(float(probs[class_idx].item()), 4)

    return {"prediction": IRIS_CLASSES[class_idx], "confidence": confidence}