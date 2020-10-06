#!/usr/bin/env python3

import itertools
import os
import re
from urllib.parse import urlparse

import requests
from discord.ext import commands

bot = commands.Bot(command_prefix='>')

tko_url_template = "https://s3.amazonaws.com/jbg-blobcast-artifacts/TeeKOGame/{}/shirtimage-{}.png"


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


if __name__ == '__main__':
    bot.run(os.getenv("TOKEN"))
