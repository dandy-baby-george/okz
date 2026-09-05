import os
import random
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

app = FastAPI()

# Discord Developer Portalから取得するPUBLIC KEY
DISCORD_PUBLIC_KEY = os.getenv("DISCORD_PUBLIC_KEY", "")
BASE_EPORNER_URL = "https://www.eporner.com/api/v2/video/search/"

def verify_discord_request(request_body: bytes, signature: str, timestamp: str):
    """Discordからのリクエストの署名を検証"""
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
        res = requests.get(BASE_EPORNER_URL, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        videos = data.get("videos", [])
        if not videos:
            return None
        selected = random.choice(videos) if is_random else videos[0]
        return normalize_eporner_item(selected)
    except Exception:
        return None

def build_embed_response(video: dict | None) -> dict:
    if not video:
        return {
            "type": 4,
            "data": {
                "content": "該当する動画が見つかりませんでした。"
            }
        }
    
    embed = {
        "title": video.get("title"),
        "url": video.get("url"),
        "color": 5814783,  # ダークパープル
        "image": {"url": video.get("thumb")} if video.get("thumb") else None,
        "fields": [
            {"name": "⏱ 再生時間", "value": f"{video.get('duration')} 分", "inline": True},
            {"name": "👀 閲覧数", "value": f"{video.get('views', 0):,}", "inline": True},
            {"name": "★ 評価", "value": f"{video.get('rate')}", "inline": True}
        ],
        "footer": {"text": f"Source: {video.get('source')}"}
    }

    return {
        "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
        "data": {
            "embeds": [embed]
        }
    }

@app.post("/api/interactions")
async def handle_interactions(request: Request):
    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")
    body = await request.body()

    if not signature or not timestamp:
        raise HTTPException(status_code=401, detail="Missing signature headers")

    verify_discord_request(body, signature, timestamp)
    data = await request.json()

    # PINGに対する手動レスポンス（Discordの接続確認用）
    if data.get("type") == 1:
        return JSONResponse(content={"type": 1})

    # Slash Command受信時の処理
    if data.get("type") == 2:
        command_name = data.get("data", {}).get("name")
        options = data.get("data", {}).get("options", [])
        
        # パラメータ取得
        query = "all"
        site = "eporner"
        for opt in options:
            if opt.get("name") == "query":
                query = opt.get("value")
            elif opt.get("name") == "site":
                site = opt.get("value")

        # コマンドごとの判定
        if site == "eporner":
            if command_name == "find-latest":
                video = fetch_eporner_video(query, "latest")
            elif command_name == "find-top-rated":
                video = fetch_eporner_video(query, "top-rated")
            elif command_name == "find-most-popular":
                video = fetch_eporner_video(query, "most-popular")
            elif command_name == "find-top-weekly":
                video = fetch_eporner_video(query, "top-weekly")
            elif command_name == "find-top-monthly":
                video = fetch_eporner_video(query, "top-monthly")
            elif command_name == "find-random":
                video = fetch_eporner_video(query, "latest", is_random=True)
            else:
                return JSONResponse(content={"type": 4, "data": {"content": "未対応のコマンドです。"}})
        else:
            # 他サイト拡張用エリア
            return JSONResponse(content={"type": 4, "data": {"content": f"未対応のサイトです: {site}"}})

        return JSONResponse(content=build_embed_response(video))

    return JSONResponse(content={"type": 4, "data": {"content": "Unknown interaction"}})
