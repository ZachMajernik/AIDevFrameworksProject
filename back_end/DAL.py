#github copilot generated the blueprint of this dal because I have never made a dal in python

import os
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient


def _serialize(document: dict) -> dict:
    """Convert a MongoDB document to a JSON-safe dict with 'id' as a string."""
    document["id"] = str(document.pop("_id"))
    return document


class ItemDAL:
    def __init__(self):
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGODB_DB", "AIDevFrameworksProject")
        collection_name = os.getenv("MONGODB_COLLECTION", "items")

        self._client = AsyncIOMotorClient(uri)
        self._collection = self._client[db_name][collection_name]

    # GET /items
    async def get_all_items(self) -> list[dict]:
        cursor = self._collection.find()
        return [_serialize(doc) async for doc in cursor]

    # GET /item/{id}
    async def get_item_by_id(self, item_id: str) -> dict | None:
        doc = await self._collection.find_one({"_id": ObjectId(item_id)})
        if doc is None:
            return None
        return _serialize(doc)

    # POST /new-item
    async def create_item(self, name: str, description: str | None) -> dict:
        result = await self._collection.insert_one(
            {"name": name, "description": description}
        )
        return await self.get_item_by_id(str(result.inserted_id))

    # PUT /update-item/{id}
    async def update_item(
        self, item_id: str, name: str, description: str | None
    ) -> dict | None:
        result = await self._collection.find_one_and_update(
            {"_id": ObjectId(item_id)},
            {"$set": {"name": name, "description": description}},
            return_document=True,
        )
        if result is None:
            return None
        return _serialize(result)

    # DELETE /delete-item/{id}
    async def delete_item(self, item_id: str) -> bool:
        result = await self._collection.delete_one({"_id": ObjectId(item_id)})
        return result.deleted_count == 1
