import asyncio
import os
import random
import re
from tempfile import TemporaryFile, TemporaryDirectory

import discord
import requests
from discord import VoiceChannel, VoiceClient
from discord.ext.commands import Context

from discord.opus import load_opus

load_opus('libopus.so.0')


async def play_sound(ctx: Context, *search_terms: str):
    search_url = "https://freesound.org/apiv2/search/text/"
    terms = []
    for term in search_terms:
        terms.append(re.sub(r'[\W]', '', term))
    if not terms:
        return

    query_params = {
        'query': f'"{" ".join(terms)}"',
        'filter': 'duration:[5 TO 10]',
        'page_size': '50',
        'fields': 'previews',
        'token': os.getenv('FREESOUND_TOKEN'),
        'sort': 'rating_desc',
    }

    try:
        response = requests.get(search_url, params=query_params)
        if response.status_code == 401:
            await ctx.send("Freesound doesn't like your token. Too bad! 😿")
            return
        response.raise_for_status()

        response_json = response.json()
        count = response_json['count']
        if not count:
            await ctx.send("That's so sad. There is no good sound for this 😿")
            return

        sound_index = random.randint(0, min(count, 20) - 1)
        sound_url = response_json['results'][sound_index]['previews']['preview-lq-mp3']
        voice_channel: VoiceChannel = ctx.author.voice.channel

        # passing the URL directly results in a delay between the bot joining and sound playing
        sound_data = requests.get(sound_url).content
        sound_file = TemporaryFile(dir=sounds_dir.name)
        sound_file.write(sound_data)
        sound_file.seek(0)

        source = discord.FFmpegOpusAudio(source=sound_file, pipe=True, options='-filter:a loudnorm')

        voice_client: VoiceClient = ctx.guild.voice_client
        if voice_client is None or voice_client.channel != voice_channel:
            await ctx.guild.change_voice_state(channel=None)
            voice_client = await voice_channel.connect()

        while True:
            try:
                voice_client.play(source)
                break
            except discord.ClientException:
                await asyncio.sleep(1)

    except requests.RequestException:
        await ctx.send("Sorry, I'm having troubles doing what you asked 😿")
        return

sounds_dir = TemporaryDirectory(dir='/dev/shm/')
