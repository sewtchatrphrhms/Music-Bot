import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os

print(discord.__version__)
print(discord.__file__)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

queues = {}
volumes = {}
current_song = {}

FFMPEG_OPTIONS = {
    "before_options":
        "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn"
}

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True
}


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Sync slash commands: {len(synced)}")
    except Exception as e:
        print(e)

    print(f"ออนไลน์เป็น {bot.user}")


async def play_next(guild):

    guild_id = guild.id
    vc = guild.voice_client

    if guild_id not in queues or len(queues[guild_id]) == 0:

        current_song[guild_id] = None

        if vc:
            await vc.disconnect()

        return

    url = queues[guild_id].pop(0)

    current_song[guild_id] = url

    try:
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(url, download=False)

            stream_url = info["url"]
            title = info.get("title", "ไม่ทราบชื่อเพลง")

        volume = volumes.get(guild_id, 0.5)

        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(
                stream_url,
                **FFMPEG_OPTIONS
            ),
            volume=volume
        )

        def after_playing(error):
            if error:
                print(error)

            asyncio.run_coroutine_threadsafe(
                play_next(guild),
                bot.loop
            )

        vc.play(source, after=after_playing)

        channel = guild.system_channel
        if channel:
            await channel.send(f"🎵 กำลังเล่น: **{title}**")

    except Exception as e:
        print(e)
        await play_next(guild)


@bot.tree.command(name="play", description="เล่นเพลงจาก YouTube")
async def play(
    interaction: discord.Interaction,
    url: str
):

    if interaction.user.voice is None:
        await interaction.response.send_message(
            "❌ เข้าห้องเสียงก่อน",
            ephemeral=True
        )
        return

    voice_channel = interaction.user.voice.channel

    vc = interaction.guild.voice_client

    if vc is None:
        vc = await voice_channel.connect()

    elif vc.channel != voice_channel:
        await interaction.response.send_message(
            "❌ คุณต้องอยู่ห้องเดียวกับบอท",
            ephemeral=True
        )
        return

    guild_id = interaction.guild.id

    if guild_id not in queues:
        queues[guild_id] = []

    queues[guild_id].append(url)

    await interaction.response.send_message(
        f"✅ เพิ่มเข้าคิวแล้ว\n{url}"
    )

    if not vc.is_playing() and not vc.is_paused():
        await play_next(interaction.guild)


@bot.tree.command(name="skip", description="ข้ามเพลง")
async def skip(interaction: discord.Interaction):

    vc = interaction.guild.voice_client

    if vc and vc.is_playing():
        vc.stop()

        await interaction.response.send_message(
            "⏭️ ข้ามเพลงแล้ว"
        )
    else:
        await interaction.response.send_message(
            "❌ ไม่มีเพลงกำลังเล่น"
        )


@bot.tree.command(name="pause", description="หยุดเพลงชั่วคราว")
async def pause(interaction: discord.Interaction):

    vc = interaction.guild.voice_client

    if vc and vc.is_playing():
        vc.pause()

        await interaction.response.send_message(
            "⏸️ หยุดเพลงชั่วคราวแล้ว"
        )
    else:
        await interaction.response.send_message(
            "❌ ไม่มีเพลงกำลังเล่น"
        )


@bot.tree.command(name="resume", description="เล่นเพลงต่อ")
async def resume(interaction: discord.Interaction):

    vc = interaction.guild.voice_client

    if vc and vc.is_paused():
        vc.resume()

        await interaction.response.send_message(
            "▶️ เล่นเพลงต่อแล้ว"
        )
    else:
        await interaction.response.send_message(
            "❌ ไม่มีเพลงที่หยุดอยู่"
        )


@bot.tree.command(
    name="volume",
    description="ปรับระดับเสียง 0-100"
)
async def volume(
    interaction: discord.Interaction,
    level: int
):

    if level < 0 or level > 100:
        await interaction.response.send_message(
            "❌ ใส่ได้แค่ 0-100"
        )
        return

    guild_id = interaction.guild.id
    volumes[guild_id] = level / 100

    vc = interaction.guild.voice_client

    if vc and vc.source:
        vc.source.volume = level / 100

    await interaction.response.send_message(
        f"🔊 ปรับเสียงเป็น {level}%"
    )


@bot.tree.command(
    name="nowplaying",
    description="ดูเพลงที่กำลังเล่น"
)
async def nowplaying(interaction: discord.Interaction):

    guild_id = interaction.guild.id

    song = current_song.get(guild_id)

    if song:
        await interaction.response.send_message(
            f"🎵 กำลังเล่น:\n{song}"
        )
    else:
        await interaction.response.send_message(
            "❌ ไม่มีเพลงกำลังเล่น"
        )


@bot.tree.command(
    name="queue",
    description="ดูคิวเพลง"
)
async def queue(interaction: discord.Interaction):

    guild_id = interaction.guild.id

    if (
        guild_id not in queues
        or len(queues[guild_id]) == 0
    ):
        await interaction.response.send_message(
            "📭 ไม่มีเพลงในคิว"
        )
        return

    queue_text = ""

    for index, song in enumerate(
        queues[guild_id],
        start=1
    ):
        queue_text += f"{index}. {song}\n"

    await interaction.response.send_message(
        f"📜 คิวเพลง:\n{queue_text}"
    )


@bot.tree.command(
    name="stop",
    description="หยุดเพลงและออกห้อง"
)
async def stop(interaction: discord.Interaction):

    guild_id = interaction.guild.id

    queues[guild_id] = []
    current_song[guild_id] = None

    vc = interaction.guild.voice_client

    if vc:
        await vc.disconnect()

    await interaction.response.send_message(
        "🛑 หยุดเพลงและออกห้องแล้ว"
    )


bot.run(os.getenv("TOKEN"))