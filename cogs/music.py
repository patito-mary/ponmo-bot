import discord
from discord.ext import commands
import yt_dlp
import asyncio

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def join_channel(self, channel: discord.VoiceChannel):
        vc = channel.guild.voice_client
        if vc:
            await vc.move_to(channel)
            return vc
        return await channel.connect()
async def play_stream(self, guild: discord.Guild, url: str):
    print("[Music] Extrayendo URL del stream...")
    
    loop = asyncio.get_event_loop()

    def extract():
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
            info = ydl.extract_info(url, download=False)
            if info.get("is_live"):
                return info["url"]
            formats = info.get("formats", [info])
            audio = next(
                (f for f in formats if f.get("acodec") != "none" and f.get("vcodec") == "none"),
                formats[-1]
            )
            return audio["url"]

    stream_url = await loop.run_in_executor(None, extract)
    print("[Music] URL extraída, conectando...")

    # Re-obtener el voice client DESPUÉS de la extracción
    vc = guild.voice_client
    if not vc or not vc.is_connected():
        print("[Music] Voice client perdido, abortando...")
        return

    if vc.is_playing():
        vc.stop()

    print("[Music] Reproduciendo...")
    vc.play(
        discord.FFmpegPCMAudio(
            stream_url,
            executable="C:\\ffmpeg\\bin\\ffmpeg.exe",
            **FFMPEG_OPTIONS
        ),
        after=lambda e: print(f"[Music] Error: {e}" if e else "[Music] Stream terminó")
    )
    vc.source = discord.PCMVolumeTransformer(vc.source)
    vc.source.volume = 0.2

    async def stop(self, guild: discord.Guild):
        vc = guild.voice_client
        if vc and vc.is_playing():
            vc.stop()

    async def disconnect(self, guild: discord.Guild):
        vc = guild.voice_client
        if vc:
            await vc.disconnect()

def setup(bot):
    bot.add_cog(Music(bot))