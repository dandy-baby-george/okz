import os
import random
import discord
from discord import app_commands
from discord.ext import commands
import requests

ORDER_MAP = {
    "featured": "featured",
    "hot": "hot",
    "most-viewed": "mostviewed",
    "top-rated": "toprated",
    "newest": "newest",
    "random": "random",
}

def fetch_pornhub_video(category="recommended"):
    api_url = "https://www.pornhub.com/webmasters/search"
    ordering = ORDER_MAP.get(category, "featured")
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

class MyBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands synced.")

bot = MyBot()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")

@bot.tree.command(name="get", description="Get a video")
@app_commands.describe(category="Select category")
@app_commands.choices(
    category=[
        app_commands.Choice(name=k, value=k) for k in ORDER_MAP.keys()
    ]
)
async def get_av(interaction: discord.Interaction, category: str = "recommended"):
    await interaction.response.defer()

    video = fetch_pornhub_video(category)

    if not video:
        await interaction.followup.send("No videos found.")
        return

    title = video.get("title")
    url = video.get("url")

    await interaction.followup.send(f"**[{category.upper()}]** {title}\n{url}")

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if TOKEN:
    bot.run(TOKEN)
