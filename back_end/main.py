from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Your Pydantic model(s) here
class Item(BaseModel):
    name: str
    description: Optional[str]

# In-memory storage
items_db: dict[int, dict] = {}
next_id: int = 1

# Your endpoints here
@app.get("/items", status_code=200) #ChatGPT said to add the status codes here so that if there is no error, this is the default status code if it worked
def get_items():
    return [
        {"id": item_id, "name": item["name"], "description": item.get("description")}
        for item_id, item in items_db.items()
    ]

@app.get("/item/{id}", status_code=200)
def get_item_by_id(id: int):
    if id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"id": id, **items_db[id]}

@app.post("/new-item", status_code=201)
def new_item(item: Item):
    global next_id
    items_db[next_id] = item.model_dump()
    next_id += 1
    return {"id": next_id - 1, **item.model_dump()}

@app.put("/update-item/{id}", status_code=200)
def update_item(id: int, item: Item):
    if id in items_db:
        items_db[id] = item.model_dump()
        return {"id": id, **item.model_dump()}
    else:
        raise HTTPException(status_code=404, detail="Item not found")

@app.delete("/delete-item/{id}", status_code=204)
def delete_item(id: int):
    if id in items_db:
        del items_db[id]
        return {"message": "Item deleted"}
    else:
        raise HTTPException(status_code=404, detail="Item not found")

# Run with: uvicorn main:app --reload