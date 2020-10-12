import asyncio
import io
import os
import random
import re
from asyncio import Queue
from dataclasses import dataclass
from tempfile import TemporaryFile, TemporaryDirectory

import aiohttp
import discord
import requests
from discord import VoiceChannel, VoiceClient, Guild
from discord.ext.commands import Context

from discord.opus import load_opus

load_opus('libopus.so.0')


class SoundPlayer:
    sound_players = {}

    @dataclass
    class Sound:
        source: io.TextIOWrapper
        voice_channel: VoiceChannel

    def __init__(self, guild: Guild):
        self.guild = guild
        self.voice_client: VoiceClient = guild.voice_client
        self.sound_queue = Queue()
        self.action_queue = Queue()

    @classmethod
    def get_or_create(cls, guild) -> 'SoundPlayer':
        if guild not in cls.sound_players:
            sound_player = cls(guild)
            cls.sound_players[guild] = sound_player
            asyncio.create_task(sound_player._run())

        return cls.sound_players[guild]

    async def play(self, source, voice_channel):
        await self.sound_queue.put(self.Sound(source, voice_channel))

    async def _push_action(self, action: str):
        max_queue_size = self.sound_queue.qsize()
        if self.voice_client.is_playing():
            max_queue_size += 1
        if self.action_queue.qsize() < max_queue_size:
            await self.action_queue.put(action)

    async def skip(self):
        await self.action_queue.put('skip')

    async def stop(self):
        await self.action_queue.put('stop')

    async def _wait_for_player(self):
        while self.voice_client.is_playing():
            await asyncio.sleep(.1)
            if not self.action_queue.empty():
                action = await self.action_queue.get()
                if action == 'skip':
                    self.voice_client.stop()
                elif action == 'stop':
                    self.voice_client.stop()
                    # clear the queues
                    while not self.sound_queue.empty():
                        await self.sound_queue.get()
                    while not self.action_queue.empty():
                        await self.action_queue.get()

    async def _run(self):
        while True:
            sound = await self.sound_queue.get()
            if self.voice_client is None:
                await self.guild.change_voice_state(channel=None)
                self.voice_client = await sound.voice_channel.connect()
            elif sound.voice_channel != self.voice_client.channel:
                await self.guild.change_voice_state(channel=sound.voice_channel)
            self.voice_client.play(sound.source)
            await self._wait_for_player()


async def queue_sound(ctx: Context, *search_terms: str):
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
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, params=query_params) as response:
                if response.status == 401:
                    await ctx.send("Freesound doesn't like your token. Too bad! 😿")
                    return
                response.raise_for_status()
                response_json = await response.json()

        count = response_json['count']
        if not count:
            await ctx.send("That's so sad. There is no good sound for this 😿")
            return

        sound_index = random.randint(0, min(count, 20) - 1)
        sound_url = response_json['results'][sound_index]['previews']['preview-lq-mp3']

        # passing the URL directly results in a delay between the bot joining and sound playing

        async with aiohttp.ClientSession() as session:
            async with session.get(sound_url) as response:
                response.raise_for_status()
                sound_data = await response.read()
        sound_file = TemporaryFile(dir=sounds_dir.name)
        sound_file.write(sound_data)
        sound_file.seek(0)

        source = discord.FFmpegOpusAudio(source=sound_file, pipe=True, options='-filter:a loudnorm')

        player = SoundPlayer.get_or_create(ctx.guild)
        await player.play(source, ctx.author.voice.channel)

    except requests.RequestException:
        await ctx.send("Sorry, I'm having troubles doing what you asked 😿")
        return


sounds_dir = TemporaryDirectory(dir='/dev/shm/')
