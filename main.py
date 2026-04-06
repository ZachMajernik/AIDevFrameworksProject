from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# Your Pydantic model(s) here

# In-memory storage
items_db: dict[int, dict] = {}
next_id: int = 1

# Your endpoints here
@app.get("/")
def read_root():
    return {"Hello": "World"}

# Run with: uvicorn main:app --reload