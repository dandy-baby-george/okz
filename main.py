import os
import random
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

COMMAND_CONFIG = {
    "get": ("RECOMMENDED", "featured"),
    "hot": ("HOT", "hot"),
    "top": ("TOP-RATED", "toprated"),
    "latest": ("LATEST", "newest"),
    "random": ("RANDOM", "random"),
}


class MyBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.session: aiohttp.ClientSession | None = None

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()

        await self.register_commands()
        await self.tree.sync()
        print("Slash commands synced.")

    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()

    async def fetch_pornhub_video(self, ordering: str) -> dict | None:
        api_url = "https://www.pornhub.com/webmasters/search"
        params = {"thumbsize": "large"}

        if ordering != "random":
            params["ordering"] = ordering

        try:
            async with self.session.get(
                api_url, params=params, timeout=10
            ) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                videos = data.get("videos", [])
                return random.choice(videos) if videos else None
        except Exception as e:
            print(f"API Error: {e}")
            return None

    async def handle_command(
        self, interaction: discord.Interaction, label: str, ordering: str
    ):
        await interaction.response.defer()
        video = await self.fetch_pornhub_video(ordering)

        if not video:
            await interaction.followup.send("No videos found.")
            return

        title = video.get("title", "No Title")
        url = video.get("url", "")
        await interaction.followup.send(f"**[{label}]** {title}\n{url}")

    async def register_commands(self):
        for cmd_name, (label, ordering) in COMMAND_CONFIG.items():

            async def command_callback(
                interaction: discord.Interaction,
                lbl=label,
                ord_val=ordering,
            ):
                await self.handle_command(interaction, lbl, ord_val)

            cmd = app_commands.Command(
                name=cmd_name,
                description=f"Get {cmd_name} video",
                callback=command_callback,
            )
            self.tree.add_command(cmd)


bot = MyBot()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")


TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if TOKEN:
    bot.run(TOKEN)
