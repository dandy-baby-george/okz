import json
import logging
import os
import random
import xml.etree.ElementTree as ET
from logging.handlers import RotatingFileHandler

import httpx
from curl_cffi.requests import AsyncSession
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

API_URL = "https://jp.pornhub.com/video/webmasterss"
COMMAND_NAME = "random"
COMMAND_DESCRIPTION = "Find and share a random video"
HTTP_TIMEOUT_SECONDS = 10
DISCORD_API_URL = "https://discord.com/api/v10"

app = FastAPI()

logger = logging.getLogger("random_bot")
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())
if not os.environ.get("VERCEL"):
    file_handler = RotatingFileHandler(
        "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    logger.addHandler(file_handler)


async def fetch_pornhub_video() -> dict | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    }

    try:
        async with AsyncSession(
            impersonate="chrome", timeout=HTTP_TIMEOUT_SECONDS
        ) as client:
            response = await client.get(API_URL, headers=headers)
            if response.status_code != 200:
                logger.warning("Video RSS returned HTTP %s", response.status_code)
                return None
            content_type = response.headers.get("content-type", "")
            response_text = response.text.strip()
            logger.info(
                "Video RSS response: region=%s status=%s content_type=%s url=%s redirects=%s body=%s",
                os.environ.get("VERCEL_REGION", "local"),
                response.status_code,
                content_type or "missing",
                str(response.url),
                len(getattr(response, "history", [])),
                response_text[:2000] or "<empty>",
            )
            if not response_text:
                logger.warning("Video RSS returned an empty response")
                return None
            try:
                root = ET.fromstring(response.content)
            except ET.ParseError:
                logger.warning(
                    "Video RSS returned invalid XML: body=%s", response_text[:200]
                )
                return None
            items = root.findall(".//item")
            videos = []
            for item in items:
                title = item.findtext("title", default="").strip()
                url = item.findtext("link", default="").strip()
                if title and url:
                    videos.append({"title": title, "url": url})
            logger.info(
                "Video RSS parsed: root=%s items=%s valid_videos=%s",
                root.tag,
                len(items),
                len(videos),
            )
            if not videos:
                logger.warning("Video RSS contained no valid videos")
            return random.choice(videos) if videos else None
    except Exception as error:
        logger.exception("RSS error: %s", error)
        return None


async def send_random_result(application_id: str, interaction_token: str) -> None:
    try:
        video = await fetch_pornhub_video()
        if not video:
            content = "No videos found."
        else:
            title = video.get("title", "No Title")
            url = video.get("url", "")
            content = f"**[RANDOM]** {title}\n{url}"

        webhook_url = (
            f"{DISCORD_API_URL}/webhooks/{application_id}/{interaction_token}"
            "/messages/@original"
        )
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = await client.patch(webhook_url, json={"content": content})
            if response.status_code == 404:
                followup_url = (
                    f"{DISCORD_API_URL}/webhooks/{application_id}/{interaction_token}"
                )
                response = await client.post(followup_url, json={"content": content})
        if response.is_error:
            logger.error(
                "Discord webhook error: status=%s body=%s",
                response.status_code,
                response.text,
            )
    except Exception as error:
        logger.exception("Interaction response error: %s", error)


def verify_discord_request(request: Request, body: bytes) -> bool:
    public_key = os.environ.get("DISCORD_PUBLIC_KEY")
    signature = request.headers.get("x-signature-ed25519")
    timestamp = request.headers.get("x-signature-timestamp")
    if not public_key or not signature or not timestamp:
        return False

    try:
        VerifyKey(bytes.fromhex(public_key)).verify(
            timestamp.encode() + body, bytes.fromhex(signature)
        )
        return True
    except (BadSignatureError, ValueError):
        return False


@app.get("/")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/interactions")
async def handle_interaction(
    request: Request, background_tasks: BackgroundTasks
) -> JSONResponse:
    body = await request.body()
    if not verify_discord_request(request, body):
        return JSONResponse({"error": "invalid request signature"}, status_code=401)

    try:
        interaction = json.loads(body)
    except json.JSONDecodeError:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    if interaction.get("type") == 1:
        return JSONResponse({"type": 1})

    if interaction.get("type") != 2:
        return JSONResponse({"error": "unsupported interaction"}, status_code=400)

    command = interaction.get("data", {}).get("name")
    if command != COMMAND_NAME:
        return JSONResponse({"error": "unknown command"}, status_code=400)

    background_tasks.add_task(
        send_random_result,
        interaction["application_id"],
        interaction["token"],
    )
    return JSONResponse({"type": 5})
