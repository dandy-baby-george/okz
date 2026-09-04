import json
import os
import random

import httpx
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

API_URL = "https://www.pornhub.com/webmasters/search"
COMMAND_NAME = "random"
COMMAND_DESCRIPTION = "Find and share a random video"
MIN_PAGE = 1
MAX_PAGE = 99
THUMB_SIZE = "large"
HTTP_TIMEOUT_SECONDS = 10
DISCORD_API_URL = "https://discord.com/api/v10"

app = FastAPI()


async def fetch_pornhub_video() -> dict | None:
        params = {
            "thumbsize": THUMB_SIZE,
            "page": random.randint(MIN_PAGE, MAX_PAGE),
        }

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
                response = await client.get(API_URL, params=params)
                if response.status_code != 200:
                    return None
                data = response.json()
                videos = data.get("videos", [])
                return random.choice(videos) if videos else None
        except Exception as e:
            print(f"API Error: {e}")
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
            print(
                "Discord webhook error: "
                f"status={response.status_code} body={response.text}"
            )
    except Exception as error:
        print(f"Interaction response error: {error}")


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
