#!/usr/bin/env python3
import asyncio
import itertools
import os
import random
import re
from tempfile import TemporaryDirectory, TemporaryFile
from urllib.parse import urlparse

import discord
import requests
from discord import VoiceChannel, VoiceClient
from discord.ext import commands
from discord.ext.commands import Context
from discord.opus import load_opus

bot = commands.Bot(command_prefix='>')

tko_url_template = "https://s3.amazonaws.com/jbg-blobcast-artifacts/TeeKOGame/{}/shirtimage-{}.png"

load_opus('libopus.so.0')

sounds_dir = TemporaryDirectory(dir='/dev/shm/')


@bot.command(url_or_id="URL (or ID) of the TKO shirts")
async def shirts(ctx, url_or_id: str):
    if not url_or_id:
        await ctx.send("You must supply a TKO shirts URL or ID")
        return

    tko_url = urlparse(url_or_id)
    tko_id = tko_url.path.rstrip('/').split('/')[-1]

    if not re.fullmatch(r'[0-9a-f]+', tko_id):
        await ctx.send("Invalid shirts URL or ID")
        return

    try:
        for i in itertools.count(start=0):
            shirt_image_url = tko_url_template.format(tko_id, str(i))
            response = requests.head(shirt_image_url)
            response.raise_for_status()
            await ctx.send(shirt_image_url)
    except requests.RequestException:
        await ctx.send("All done!")
        return


@bot.command(search_term="The thing to search for")
async def img(ctx, *search_terms: str):
    search_url = "https://source.unsplash.com/random"
    terms = []
    for term in search_terms:
        terms.append(re.sub(r'[\W]', '', term))
    if not terms:
        return

    try:
        response = requests.head(search_url, params=','.join(terms))
        response.raise_for_status()
        await ctx.send(response.next.url)
    except requests.RequestException:
        await ctx.send("Sorry, I'm having troubles doing what you asked 😿")
        return


@bot.command(search_term="The thing to search for")
async def sound(ctx: Context, *search_terms: str):
    await play_sound(ctx, *search_terms)


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

        # passing the URL directly results in a delay between the bot joining and sound playing
        sound_data = requests.get(sound_url).content
        sound_file = TemporaryFile(dir=sounds_dir.name)
        sound_file.write(sound_data)
        sound_file.seek(0)

        source = discord.FFmpegOpusAudio(source=sound_file, pipe=True, options='-filter:a loudnorm')
        voice_channel: VoiceChannel = ctx.author.voice.channel

        voice_client: VoiceClient = ctx.guild.voice_client
        if voice_client is None:
            await ctx.guild.change_voice_state(channel=None)
            voice_client = await voice_channel.connect()
        if voice_client.channel != voice_channel:
            await ctx.guild.change_voice_state(channel=voice_channel)

        while True:
            try:
                voice_client.play(source)
                break
            except discord.ClientException:
                await asyncio.sleep(1)

    except requests.RequestException:
        await ctx.send("Sorry, I'm having troubles doing what you asked 😿")
        return


if __name__ == '__main__':
    bot.run(os.getenv("TOKEN"))
