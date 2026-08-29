import os
import random
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

API_URL = "https://www.pornhub.com/webmasters/search"
COMMAND_NAME = "random"
COMMAND_DESCRIPTION = "Find and share a random video"
MIN_PAGE = 1
MAX_PAGE = 99
THUMB_SIZE = "large"
HTTP_TIMEOUT_SECONDS = 10


class MyBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.session: aiohttp.ClientSession | None = None

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()

        @self.tree.command(name=COMMAND_NAME, description=COMMAND_DESCRIPTION)
        async def random_command(interaction: discord.Interaction):
            await interaction.response.defer()
            video = await self.fetch_pornhub_video()

            if not video:
                await interaction.followup.send("No videos found.")
                return

            title = video.get("title", "No Title")
            url = video.get("url", "")
            await interaction.followup.send(f"**[RANDOM]** {title}\n{url}")

        await self.tree.sync()
        print("Slash commands synced.")

    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()

    async def fetch_pornhub_video(self) -> dict | None:
        params = {
            "thumbsize": THUMB_SIZE,
            "page": random.randint(MIN_PAGE, MAX_PAGE),
        }

        try:
            async with self.session.get(
                API_URL, params=params, timeout=HTTP_TIMEOUT_SECONDS
            ) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                videos = data.get("videos", [])
                return random.choice(videos) if videos else None
        except Exception as e:
            print(f"API Error: {e}")
            return None


bot = MyBot()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")


TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if TOKEN:
    bot.run(TOKEN)
