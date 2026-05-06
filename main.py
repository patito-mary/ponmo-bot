import discord
from dotenv import load_dotenv
import os
import asyncio
from database import init_db

load_dotenv()

bot = discord.Bot(intents=discord.Intents.all())

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

async def main():
    await init_db()
    bot.load_extension("cogs.music")
    bot.load_extension("cogs.pomodoro")
    await bot.start(os.getenv("DISCORD_TOKEN"))

asyncio.run(main())