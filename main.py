import os
import random
import discord
from discord.ext import commands
import requests

# インテントの設定
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

ORDER_MAP = {
    "おすすめ": "featured",
    "最もホット": "hot",
    "最多閲覧": "mostviewed",
    "最高評価": "toprated",
    "最新": "newest",
    "ランダム": "random",
}


def fetch_pornhub_video(order_key="おすすめ"):
    api_url = "https://www.pornhub.com/webmasters/search"
    ordering = ORDER_MAP.get(order_key, "featured")
    params = {"thumbsize": "large"}

    if ordering != "random":
        params["ordering"] = ordering

    try:
        response = requests.get(api_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        videos = data.get("videos", [])
        if not videos:
            return None
        return random.choice(videos)
    except Exception as e:
        print(f"API Error: {e}")
        return None


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")


@bot.command(name="av")
async def get_av(ctx, category: str = "おすすめ"):
    """使用例: !av 最もホット / !av 最高評価 / !av ランダム"""
    if category not in ORDER_MAP:
        categories_str = " / ".join(ORDER_MAP.keys())
        await ctx.send(f"カテゴリを指定してください: `{categories_str}`")
        return

    video = fetch_pornhub_video(category)

    if not video:
        await ctx.send("動画が見つかりませんでした。")
        return

    title = video.get("title")
    url = video.get("url")

    await ctx.send(f"**【{category}】** {title}\n{url}")


# 環境変数からトークンを取得して起動
TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if TOKEN:
    bot.run(TOKEN)