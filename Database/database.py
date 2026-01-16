import os
import motor.motor_asyncio
import time

DATABASE_URI = os.getenv("DATABASE_URI","mongodb+srv://HARSHA24:HARSHA24@cluster0.sxaj8up.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
DATABASE_NAME = os.getenv("DATABASE_NAME", "GroupScannerBot")


class Database:
    def __init__(self):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(DATABASE_URI)
        self.db = self.client[DATABASE_NAME]

        self.settings = self.db.settings
        self.warns = self.db.warns
        self.logs = self.db.logs
        self.bans = self.db.bans
        self.user_stats = self.db.user_stats

    # ================= SETTINGS =================
    async def get_settings(self, chat_id: int):
        default = {
            "enabled": True,
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

    # ================= WARNS =================
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

    async def get_warns(self, chat_id: int, user_id: int):
        doc = await self.warns.find_one({"chat_id": chat_id, "user_id": user_id})
        return doc["count"] if doc else 0

    # ================= LOG NSFW =================
    async def log_restricted(self, chat_id, user_id, file, reasons):
        await self.logs.insert_one({
            "chat_id": chat_id,
            "user_id": user_id,
            "file": file,
            "reasons": reasons,
            "time": int(time.time())
        })

    async def get_last_log(self, chat_id, user_id):
        return await self.logs.find_one(
            {"chat_id": chat_id, "user_id": user_id},
            sort=[("time", -1)]
        )

    # ================= BANS =================
    async def ban_user(self, chat_id, user_id, reason):
        await self.bans.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {"$set": {
                "reason": reason,
                "time": int(time.time())
            }},
            upsert=True
        )

    async def unban_user(self, chat_id, user_id):
        await self.bans.delete_one(
            {"chat_id": chat_id, "user_id": user_id}
        )

    async def is_user_banned(self, chat_id, user_id):
        return await self.bans.find_one(
            {"chat_id": chat_id, "user_id": user_id}
        ) is not None

    async def get_ban_info(self, chat_id, user_id):
        return await self.bans.find_one(
            {"chat_id": chat_id, "user_id": user_id}
        )

    # ================= GLOBAL USER STATS =================
    async def inc_user_warn(self, user_id: int):
        await self.user_stats.update_one(
            {"user_id": user_id},
            {"$inc": {"warns": 1}},
            upsert=True
        )

    async def inc_user_ban(self, user_id: int):
        await self.user_stats.update_one(
            {"user_id": user_id},
            {"$inc": {"bans": 1}},
            upsert=True
        )

    async def get_user_stats(self, user_id: int):
        doc = await self.user_stats.find_one({"user_id": user_id})
        return {
            "warns": doc.get("warns", 0) if doc else 0,
            "bans": doc.get("bans", 0) if doc else 0
        }

    async def count_warned_users(self):
        return await self.warns.count_documents({})

    async def count_banned_users(self):
        return await self.bans.count_documents({})

    async def get_warned_users(self):
        cursor = self.warns.find({}, {"_id": 0, "user_id": 1})
        return [doc["user_id"] async for doc in cursor]

    async def get_banned_users(self):
        cursor = self.bans.find({}, {"_id": 0, "user_id": 1})
        return [doc["user_id"] async for doc in cursor]


db = Database()
