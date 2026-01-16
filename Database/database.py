import os
import motor.motor_asyncio

DATABASE_URI = os.getenv("DATABASE_URI","mongodb+srv://HARSHA24:HARSHA24@cluster0.sxaj8up.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
DATABASE_NAME = os.getenv("DATABASE_NAME", "GroupScannerBot")

class Database:
    def __init__(self):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(DATABASE_URI)
        self.db = self.client[DATABASE_NAME]

        self.settings = self.db.settings
        self.warns = self.db.warns
        self.logs = self.db.logs

    # -------- SETTINGS --------
    async def get_settings(self, chat_id: int):
        default = {
            "enabled": True,
            "warn_limit": 3,
            "silent_delete": False,
            "auto_ban": True,
            "adult_threshold": 0.15,
            "frame_fps": 2,
            "scan_audio": True
        }
        data = await self.settings.find_one({"chat_id": chat_id})
        return {**default, **data} if data else default

    async def update_setting(self, chat_id: int, key: str, value):
        await self.settings.update_one(
            {"chat_id": chat_id},
            {"$set": {key: value}},
            upsert=True
        )

    # -------- WARNS --------
    async def add_warn(self, chat_id: int, user_id: int):
        doc = await self.warns.find_one({"chat_id": chat_id, "user_id": user_id})
        count = doc["count"] + 1 if doc else 1
        await self.warns.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {"$set": {"count": count}},
            upsert=True
        )
        return count

    async def reset_warns(self, chat_id: int, user_id: int):
        await self.warns.delete_one({"chat_id": chat_id, "user_id": user_id})

    # -------- LOG --------
    async def log_restricted(self, data: dict):
        await self.logs.insert_one(data)

db = Database()
