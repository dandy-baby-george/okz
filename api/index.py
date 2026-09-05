import os
import random
import requests
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

app = FastAPI()

DISCORD_PUBLIC_KEY = os.getenv("DISCORD_PUBLIC_KEY", "")
BASE_EPORNER_URL = "https://www.eporner.com/api/v2/video/search/"

def verify_discord_request(request_body: bytes, signature: str, timestamp: str):
    if not DISCORD_PUBLIC_KEY:
        raise HTTPException(status_code=500, detail="DISCORD_PUBLIC_KEY is not configured")
    try:
        verify_key = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))
        verify_key.verify(timestamp.encode() + request_body, bytes.fromhex(signature))
    except BadSignatureError:
        raise HTTPException(status_code=401, detail="Invalid request signature")

def normalize_eporner_item(v: dict) -> dict:
    return {
        "id": v.get("id"),
        "title": v.get("title"),
        "url": v.get("url"),
        "thumb": v.get("default_thumb", {}).get("src"),
        "duration": v.get("length_min"),
        "views": v.get("views"),
        "rate": v.get("rate"),
        "source": "EPORNER"
    }

def fetch_eporner_video(query: str, order: str, is_random: bool = False) -> dict | None:
    page = random.randint(1, 20) if is_random else 1
    params = {
        "query": query,
        "per_page": 30 if is_random else 1,
        "page": page,
        "order": order,
        "gay": 0,
        "lq": 0,
        "format": "json"
    }
    try:
        res = requests.get(BASE_EPORNER_URL, params=params, timeout=8)
        res.raise_for_status()
        data = res.json()
        videos = data.get("videos", [])
        if not videos:
            return None
        selected = random.choice(videos) if is_random else videos[0]
        return normalize_eporner_item(selected)
    except Exception:
        return None

def process_command_and_followup(token: str, app_id: str, command_name: str, query: str, site: str):
    followup_url = f"https://discord.com/api/v10/webhooks/{app_id}/{token}/messages/@original"
    
    video = None
    if site == "eporner":
        if command_name == "latest":
            video = fetch_eporner_video(query, "latest")
        elif command_name == "top-rated":
            video = fetch_eporner_video(query, "top-rated")
        elif command_name == "most-popular":
            video = fetch_eporner_video(query, "most-popular")
        elif command_name == "top-weekly":
            video = fetch_eporner_video(query, "top-weekly")
        elif command_name == "top-monthly":
            video = fetch_eporner_video(query, "top-monthly")
        elif command_name == "random":
            video = fetch_eporner_video(query, "latest", is_random=True)

    if not video:
        payload = {"content": "該当する動画が見つかりませんでした。"}
    else:
        embed = {
            "title": video.get("title"),
            "url": video.get("url"),
            "color": 5814783,
            "image": {"url": video.get("thumb")} if video.get("thumb") else None,
            "fields": [
                {"name": "⏱ 再生時間", "value": f"{video.get('duration')} 分", "inline": True},
                {"name": "👀 閲覧数", "value": f"{video.get('views', 0):,}", "inline": True},
                {"name": "★ 評価", "value": f"{video.get('rate')}", "inline": True}
            ],
            "footer": {"text": f"Source: {video.get('source')}"}
        }
        payload = {"embeds": [embed]}

    try:
        requests.patch(followup_url, json=payload, timeout=10)
    except Exception as e:
        print(f"Failed to send followup: {e}")

@app.post("/")
@app.post("/api/interactions")
async def handle_interactions(request: Request, background_tasks: BackgroundTasks):
    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")
    body = await request.body()

    if not signature or not timestamp:
        raise HTTPException(status_code=401, detail="Missing signature headers")

    verify_discord_request(body, signature, timestamp)
    data = await request.json()

    if data.get("type") == 1:
        return JSONResponse(content={"type": 1})

    if data.get("type") == 2:
        token = data.get("token")
        app_id = data.get("application_id")
        command_name = data.get("data", {}).get("name")
        options = data.get("data", {}).get("options", [])

        query = "all"
        site = "eporner"
        for opt in options:
            if opt.get("name") == "query":
                query = opt.get("value")
            elif opt.get("name") == "site":
                site = opt.get("value")

        background_tasks.add_task(
            process_command_and_followup,
            token, app_id, command_name, query, site
        )

        return JSONResponse(content={"type": 5})

    return JSONResponse(content={"type": 4, "data": {"content": "Unknown interaction"}})
