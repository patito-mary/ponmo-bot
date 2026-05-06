import discord
from discord.ext import commands
import asyncio
import json

from database import (
    create_session, get_session, use_unmute,
    set_phase, end_session
)

with open("data/playlists.json", encoding="utf-8") as f:
    PLAYLISTS = json.load(f)["playlists"]

PLAYLIST_CHOICES = [
    discord.OptionChoice(name=f"{p['emoji']} {p['name']}", value=p["id"])
    for p in PLAYLISTS
]

UNMUTE_DURATION = 30  # segundos que dura el desmuteo manual

class Pomodoro(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tasks: dict[int, asyncio.Task] = {}  # guild_id -> Task

    # ─── /start-pom ────────────────────────────────────────────
    @discord.slash_command(name="start-pom", description="🍅 Inicia un pomodoro")
    @discord.option("duration", description="Minutos de trabajo (default: 25)", required=False, default=25, min_value=1, max_value=120)
    @discord.option("break_time", description="Minutos de descanso (default: 5)", required=False, default=5, min_value=1, max_value=30)
    @discord.option("playlist", description="Playlist de lofi", required=False, choices=PLAYLIST_CHOICES, default="lofi_girl")
    async def start_pom(self, ctx: discord.ApplicationContext, duration: int, break_time: int, playlist: str):

        if not ctx.author.voice:
            return await ctx.respond("❌ Debes estar en un canal de voz.", ephemeral=True)

        if await get_session(ctx.guild_id):
            return await ctx.respond("❌ Ya hay un pomodoro activo en este servidor.", ephemeral=True)

        channel = ctx.author.voice.channel
        playlist_info = next(p for p in PLAYLISTS if p["id"] == playlist)

        await create_session(ctx.guild_id, ctx.author.id, channel.id, duration, break_time, playlist)

        # Mutear a todos los humanos en el canal
        muted = []
        for member in channel.members:
            if not member.bot:
                try:
                    await member.edit(mute=True, reason="Sesión Pomodoro activa")
                    muted.append(member)
                except discord.Forbidden:
                    pass

        # Unirse y reproducir música
        music: Music = self.bot.get_cog("Music")
        await music.join_channel(channel)
        await music.play_stream(ctx.guild, playlist_info["url"])

        await ctx.respond(
            f"🍅 **Pomodoro iniciado** — {duration} min de trabajo · {break_time} min de descanso\n"
            f"{playlist_info['emoji']} Reproduciendo: **{playlist_info['name']}**\n"
            f"🔇 {len(muted)} usuario(s) muteados\n"
            f"💬 Usa `/unmute` para un desmuteo temporal (3 disponibles)"
        )

        # Lanzar el ciclo del pomodoro
        task = asyncio.create_task(
            self._run_cycle(ctx, channel, duration, break_time, playlist_info)
        )
        self.tasks[ctx.guild_id] = task

    # ─── /stop-pom ─────────────────────────────────────────────
    @discord.slash_command(name="stop-pom", description="⏹️ Detiene el pomodoro actual")
    async def stop_pom(self, ctx: discord.ApplicationContext):
        session = await get_session(ctx.guild_id)
        if not session:
            return await ctx.respond("❌ No hay ningún pomodoro activo.", ephemeral=True)

        await self._finalizar_sesion(ctx.guild, session["channel_id"])
        await ctx.respond("⏹️ Pomodoro detenido. ¡Todos desmuteados!")

    # ─── /unmute ───────────────────────────────────────────────
    @discord.slash_command(name="unmute", description="🔊 Usa uno de tus desmuteos temporales (3 por sesión)")
    async def unmute(self, ctx: discord.ApplicationContext):
        session = await get_session(ctx.guild_id)
        if not session:
            return await ctx.respond("❌ No hay ningún pomodoro activo.", ephemeral=True)

        if session["phase"] != "work":
            return await ctx.respond("ℹ️ Estás en el descanso, ya estás desmuteado.", ephemeral=True)

        remaining = await use_unmute(ctx.guild_id)
        if remaining == 0 and session["unmutes_left"] == 0:
            return await ctx.respond("❌ Ya no tienes desmuteos disponibles para esta sesión.", ephemeral=True)

        try:
            await ctx.author.edit(mute=False)
        except discord.Forbidden:
            return await ctx.respond("❌ No tengo permisos para desmutearte.", ephemeral=True)

        await ctx.respond(
            f"🔊 Desmuteado por {UNMUTE_DURATION} segundos.\n"
            f"💬 Desmuteos restantes: **{remaining}/3**",
            ephemeral=True
        )

        # Re-mutear después del tiempo
        await asyncio.sleep(UNMUTE_DURATION)

        current = await get_session(ctx.guild_id)
        if current and current["phase"] == "work":
            try:
                await ctx.author.edit(mute=True)
            except Exception:
                pass

    # ─── /pom-status ───────────────────────────────────────────
    @discord.slash_command(name="pom-status", description="📊 Estado del pomodoro actual")
    async def pom_status(self, ctx: discord.ApplicationContext):
        session = await get_session(ctx.guild_id)
        if not session:
            return await ctx.respond("❌ No hay ningún pomodoro activo.", ephemeral=True)

        phase_emoji = "💼" if session["phase"] == "work" else "☕"
        phase_name  = "Trabajo" if session["phase"] == "work" else "Descanso"
        playlist    = next((p for p in PLAYLISTS if p["id"] == session["playlist_id"]), PLAYLISTS[0])

        embed = discord.Embed(title="🍅 Estado del Pomodoro", color=discord.Color.red())
        embed.add_field(name="Fase actual",     value=f"{phase_emoji} {phase_name}",          inline=True)
        embed.add_field(name="Trabajo",         value=f"{session['duration']} min",            inline=True)
        embed.add_field(name="Descanso",        value=f"{session['break_time']} min",          inline=True)
        embed.add_field(name="Playlist",        value=f"{playlist['emoji']} {playlist['name']}", inline=True)
        embed.add_field(name="Desmuteos left",  value=f"💬 {session['unmutes_left']}/3",       inline=True)

        await ctx.respond(embed=embed)

    # ─── Lógica interna ────────────────────────────────────────
    async def _run_cycle(self, ctx, channel, duration, break_time, playlist_info):
        try:
            # === FASE DE TRABAJO ===
            await asyncio.sleep(duration * 60)

            session = await get_session(ctx.guild_id)
            if not session:
                return

            music: Music = self.bot.get_cog("Music")
            await music.stop(ctx.guild)
            await set_phase(ctx.guild_id, "break")

            # Desmutear a todos
            for member in channel.members:
                if not member.bot:
                    try:
                        await member.edit(mute=False)
                    except Exception:
                        pass

            await ctx.channel.send(
                f"✅ **¡Pomodoro completado!** Tómate un descanso de {break_time} minutos. ☕\n"
                f"*Todos han sido desmuteados.*"
            )

            # === FASE DE DESCANSO ===
            await asyncio.sleep(break_time * 60)

            await ctx.channel.send(
                "⏰ **¡Descanso terminado!** El pomodoro ha finalizado.\n"
                "Usa `/start-pom` para iniciar otro ciclo."
            )

        except asyncio.CancelledError:
            pass  # Cancelado por /stop-pom
        finally:
            await self._finalizar_sesion(ctx.guild, channel.id)

    async def _finalizar_sesion(self, guild: discord.Guild, channel_id: int):
        # Cancelar tarea si existe
        task = self.tasks.pop(guild.id, None)
        if task and not task.done():
            task.cancel()

        # Desmutear a todos
        channel = guild.get_channel(channel_id)
        if channel:
            for member in channel.members:
                if not member.bot:
                    try:
                        await member.edit(mute=False)
                    except Exception:
                        pass

        # Detener música y desconectar
        music: Music = self.bot.get_cog("Music")
        await music.stop(guild)
        await music.disconnect(guild)

        await end_session(guild.id)

def setup(bot):
    bot.add_cog(Pomodoro(bot))