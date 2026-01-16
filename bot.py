
import os, time, json, subprocess
from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from nudenet import NudeDetector
import whisper

from Database.database import db

# ============ CONFIG ============
API_ID = 10811400
API_HASH = "191bf5ae7a6c39771e7b13cf4ffd1279"
BOT_TOKEN = "6626666215:AAFSI_ZRp6aoTy9boDgxkrd_2PjyT4myeGg"


DOWNLOAD_DIR = "downloads"
FRAMES_DIR = "frames"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(FRAMES_DIR, exist_ok=True)

detector = NudeDetector()
whisper_model = whisper.load_model("base")

app = Client(
    "GroupScannerBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ============ CONSTANTS ============
NSFW_CLASSES = {
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_EXPOSED",
    "BREAST_EXPOSED",
    "BUTTOCKS_EXPOSED",
    "FEMALE_UNDERWEAR",
    "MALE_UNDERWEAR"
}

FILENAME_KEYWORDS = ["18", "porn", "xxx", "adult", "sex", "ashleel"]
AUDIO_KEYWORDS = ["sex", "fuck", "porn", "nude"]

# ============ HELPERS ============
def admin_only(_, __, m: Message):
    return m.from_user and m.from_user.is_chat_admin

def ffprobe_info(path):
    cmd = ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path]
    return json.loads(subprocess.run(cmd, capture_output=True, text=True).stdout)

def extract_frames(video, fps):
    for f in os.listdir(FRAMES_DIR):
        os.remove(os.path.join(FRAMES_DIR, f))
    subprocess.run(
        ["ffmpeg", "-i", video, "-vf", f"fps={fps}", f"{FRAMES_DIR}/f_%03d.jpg", "-y"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def detect_adult_video(threshold):
    hits, total = 0, 0
    for img in os.listdir(FRAMES_DIR):
        dets = detector.detect(os.path.join(FRAMES_DIR, img))
        for d in dets:
            if d["class"] in NSFW_CLASSES:
                hits += 1
                break
        total += 1
    return (hits / total) >= threshold if total else False

def detect_explicit_audio(path):
    text = whisper_model.transcribe(path)["text"].lower()
    return any(w in text for w in AUDIO_KEYWORDS)

# ============ INLINE SETTINGS ============
def settings_keyboard(settings):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"Scanner: {'ON' if settings['enabled'] else 'OFF'}",
                callback_data="toggle_enabled"
            )
        ],
        [
            InlineKeyboardButton(
                f"Silent Delete: {'ON' if settings['silent_delete'] else 'OFF'}",
                callback_data="toggle_silent"
            )
        ],
        [
            InlineKeyboardButton(
                f"Auto Ban: {'ON' if settings['auto_ban'] else 'OFF'}",
                callback_data="toggle_autoban"
            )
        ]
    ])

@app.on_message(filters.command("settings") & filters.group & filters.create(admin_only))
async def settings_cmd(_, m: Message):
    s = await db.get_settings(m.chat.id)
    await m.reply(
        f"⚙️ **Group Settings**\n\n"
        f"🆔 Group ID: `{m.chat.id}`\n"
        f"👥 Group: {m.chat.title}\n\n"
        f"Warn limit: {s['warn_limit']}\n"
        f"Adult threshold: {s['adult_threshold']}\n"
        f"Frame FPS: {s['frame_fps']}\n"
        f"Audio scan: {s['scan_audio']}",
        reply_markup=settings_keyboard(s)
    )

@app.on_callback_query()
async def settings_callback(_, q: CallbackQuery):
    chat_id = q.message.chat.id
    s = await db.get_settings(chat_id)

    if q.data == "toggle_enabled":
        await db.update_setting(chat_id, "enabled", not s["enabled"])
    elif q.data == "toggle_silent":
        await db.update_setting(chat_id, "silent_delete", not s["silent_delete"])
    elif q.data == "toggle_autoban":
        await db.update_setting(chat_id, "auto_ban", not s["auto_ban"])

    s = await db.get_settings(chat_id)
    await q.message.edit_reply_markup(settings_keyboard(s))
    await q.answer("Updated")

# ============ SCANNER (GROUP ONLY) ============
@app.on_message(filters.video | filters.audio | filters.document)
async def scanner(client, m: Message):
    if m.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    settings = await db.get_settings(m.chat.id)
    if not settings["enabled"]:
        return

    file = m.video or m.audio or m.document
    path = await m.download(file_name=DOWNLOAD_DIR)

    info = ffprobe_info(path)
    has_video = any(s["codec_type"] == "video" for s in info["streams"])
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])

    restricted = False
    reasons = []

    if any(k in file.file_name.lower() for k in FILENAME_KEYWORDS):
        restricted, reasons = True, ["Filename"]

    if not restricted and has_video:
        extract_frames(path, settings["frame_fps"])
        if detect_adult_video(settings["adult_threshold"]):
            restricted, reasons = True, ["Video"]

    if not restricted and has_audio and settings["scan_audio"]:
        if detect_explicit_audio(path):
            restricted, reasons = True, ["Audio"]

    if restricted:
        try:
            await client.delete_messages(m.chat.id, m.id)
        except:
            pass

        warns = await db.add_warn(m.chat.id, m.from_user.id)

        if warns >= settings["warn_limit"] and settings["auto_ban"]:
            await client.ban_chat_member(m.chat.id, m.from_user.id)
            await db.reset_warns(m.chat.id, m.from_user.id)

        if not settings["silent_delete"]:
            await client.send_message(
                m.chat.id,
                f"⚠️ {m.from_user.mention} warned ({warns}/{settings['warn_limit']})"
            )

        await db.log_restricted({
            "chat_id": m.chat.id,
            "user_id": m.from_user.id,
            "file": file.file_name,
            "reasons": reasons,
            "time": int(time.time())
        })

    os.remove(path)

print("✅ Group Scanner Bot Running")
app.run()
