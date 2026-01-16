import os, time, json, subprocess
from typing import Dict
from pyrogram import Client, filters
from nudenet import NudeClassifier
import whisper

# ---------------- CONFIG ----------------
API_ID = 10811400
API_HASH = "191bf5ae7a6c39771e7b13cf4ffd1279"
BOT_TOKEN = "6626666215:AAFSI_ZRp6aoTy9boDgxkrd_2PjyT4myeGg"

DOWNLOAD_DIR = "downloads"
FRAMES_DIR = "frames"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(FRAMES_DIR, exist_ok=True)

classifier = NudeClassifier()
whisper_model = whisper.load_model("base")

app = Client(
    "MediaScannerBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ---------------- FAST PROGRESS BAR ----------------
def progress_bar(current: int, total: int, task: Dict):
    now = time.time()
    if "last_edit" in task and now - task["last_edit"] < 2:
        return
    task["last_edit"] = now

    diff = now - task["start_time"]
    diff = diff if diff != 0 else 1
    speed = current / diff
    eta = (total - current) / speed if speed else 0
    percent = current * 100 / total

    bar_len = 20
    filled = int(bar_len * current / total)
    bar = "█" * filled + "░" * (bar_len - filled)

    msg = (
        f"{task['action']} [{bar}] {percent:.0f}%\n"
        f"Speed: {speed / (1024*1024):.2f} MB/s\n"
        f"ETA: {int(eta)} sec"
    )

    try:
        task["message"].edit_text(msg)
    except:
        pass

# ---------------- MEDIA UTILITIES ----------------
def ffprobe_info(path):
    cmd = ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path]
    out = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(out.stdout)

def extract_frames(video):
    for f in os.listdir(FRAMES_DIR):
        os.remove(os.path.join(FRAMES_DIR, f))
    subprocess.run(
        ["ffmpeg", "-i", video, "-vf", "fps=1", f"{FRAMES_DIR}/frame_%03d.jpg", "-y"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

def detect_adult_video():
    unsafe = 0
    total = 0
    for img in os.listdir(FRAMES_DIR):
        path = os.path.join(FRAMES_DIR, img)
        res = classifier.classify(path)
        if res[path]["unsafe"] > 0.7:
            unsafe += 1
        total += 1
    return (unsafe / total) if total else 0

def detect_explicit_audio(path):
    text = whisper_model.transcribe(path)["text"].lower()
    words = ["sex", "fuck", "porn", "nude", "xxx"]
    return any(w in text for w in words)

# ---------------- BOT COMMAND ----------------
@app.on_message(filters.video | filters.audio | filters.document)
async def scan_handler(client, message):
    task = {
        "action": "📥 Downloading",
        "start_time": time.time(),
        "message": await message.reply("📥 Downloading...")
    }

    file = message.video or message.audio or message.document
    path = await message.download(
        file_name=DOWNLOAD_DIR,
        progress=progress_bar,
        progress_args=(task,)
    )

    task["action"] = "🔍 Scanning"
    await task["message"].edit_text("🔍 Scanning file...")

    info = ffprobe_info(path)
    duration = float(info["format"].get("duration", 0))
    size = os.path.getsize(path) / (1024 * 1024)

    video, audio = None, None
    for s in info["streams"]:
        if s["codec_type"] == "video":
            video = s
        if s["codec_type"] == "audio":
            audio = s

    adult = "N/A"
    restricted = False

    if video:
        extract_frames(path)
        ratio = detect_adult_video()
        adult = f"YES ({ratio*100:.0f}%)" if ratio > 0.3 else "NO"
        restricted = ratio > 0.3

    if audio:
        explicit = detect_explicit_audio(path)
        restricted = restricted or explicit

    report = (
        f"📁 File: {file.file_name}\n"
        f"📦 Size: {size:.2f} MB\n"
        f"⏱ Duration: {int(duration)} sec\n"
        f"🎥 Video: {'YES' if video else 'NO'}\n"
        f"🎵 Audio: {'YES' if audio else 'NO'}\n"
        f"🔞 Adult Content: {adult}\n"
        f"🚫 Restricted: {'YES' if restricted else 'NO'}"
    )

    await task["message"].edit_text(report)
    os.remove(path)

# ---------------- START ----------------
print("✅ Media Scanner Bot Running")


app.run()
