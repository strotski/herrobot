import discord
import requests
import os
import asyncio
from playwright.async_api import async_playwright, TimeoutError
import re

# Initialize the discord client
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Directory to save images
img_dir = "hero_images"
os.makedirs(img_dir, exist_ok=True)

# Store cached heroes data
cached_heroes_data = []
hero_mapping = {}  # Maps normalized names or URL parts to hero names

# Function to normalize names for easier searching
def normalize_name(name):
    return re.sub(r'\W+', '', name).lower()

# Asynchronous function to scrape the website and return all hero data
async def scrape_heroes():
    global cached_heroes_data, hero_mapping
    heroes_data = []
    hero_mapping = {}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Add headers to prevent caching
            await page.set_extra_http_headers({
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            })

            url = "https://fantasydata.xyz/"  # Replace with the actual URL
            await page.goto(url)

            try:
                await page.wait_for_load_state("networkidle", timeout=30000)
            except TimeoutError:
                print("Page loading timed out.")
                await browser.close()
                return

            # Get all rows from the hero table
            rows = await page.query_selector_all("#heroTable tr")
            print(f"Number of rows fetched: {len(rows)}")  # Debugging output
            rows = rows[1:]  # Skip the header row

            for index, row in enumerate(rows):
                cells = await row.query_selector_all("td")
                if len(cells) < 10:
                    continue

                hero_name = (await cells[1].inner_text()).strip()
                profile_anchor = await cells[1].query_selector("a")
                profile_url = await profile_anchor.get_attribute("href")
                normalized_url = normalize_name(profile_url)
                normalized_name = normalize_name(hero_name)

                img_element = await cells[0].query_selector("img")
                img_url = await img_element.get_attribute("src")

                # Download the image
                img_response = requests.get(img_url)
                img_filename = f"hero_{index + 1}.jpg"
                img_path = os.path.join(img_dir, img_filename)

                with open(img_path, "wb") as img_file:
                    img_file.write(img_response.content)

                hero = {
                    "IMG": img_path,
                    "Hero Name": hero_name,
                    "Rank": (await cells[2].inner_text()).strip(),
                    "Score": (await cells[3].inner_text()).strip(),
                    "Score %": (await cells[4].inner_text()).strip(),
                    "Cards": (await cells[5].inner_text()).strip(),
                    "Cards +/-": (await cells[6].inner_text()).strip(),
                    "Floor": (await cells[7].inner_text()).strip(),
                    "Floor %": (await cells[8].inner_text()).strip(),
                    "Followers": (await cells[9].inner_text()).strip(),
                    "Views": (await cells[10].inner_text()).strip()
                }
                heroes_data.append(hero)

                hero_mapping[normalized_url] = hero_name
                hero_mapping[normalized_name] = hero_name

            await browser.close()
    except Exception as e:
        print(f"An error occurred during scraping: {e}")

    cached_heroes_data = heroes_data
    print("Updated cached heroes data")
    print("All available hero names:")
    for hero in cached_heroes_data:
        print(f" - {hero['Hero Name']}")

# Function to find and return stats of a hero by either name or URL
async def get_hero_stats(hero_input):
    normalized_input = normalize_name(hero_input)
    print(f"Searching for hero by input: {normalized_input}")

    for identifier, full_name in hero_mapping.items():
        if normalized_input in identifier:
            print(f"Match found: {full_name}")
            for hero in cached_heroes_data:
                if hero["Hero Name"] == full_name:
                    return hero

    print("Hero not found via either URL or name")
    return None

# Background task that periodically updates the cached data
async def periodic_update():
    while True:
        try:
            await scrape_heroes()
        except Exception as e:
            print(f"Error during periodic update: {e}")
        await asyncio.sleep(300)

# Discord event when the bot is ready
@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    client.loop.create_task(periodic_update())

# Discord event to handle messages
@client.event
async def on_message(message):
    if message.author == client.user or message.author.bot:
        return

    print(f"Received message: {message.content}")

    if message.content.startswith('!hero'):
        print("!hero command detected")
        hero_name_input = message.content[len('!hero '):].strip()
        hero_stats = await get_hero_stats(hero_name_input)

        if hero_stats:
            embed = discord.Embed(
                title=f"Stats for {hero_stats['Hero Name']}",
                color=discord.Color.blue()
            )

            embed.add_field(name="Rank", value=hero_stats["Rank"], inline=True)
            embed.add_field(name="Score", value=hero_stats["Score"], inline=True)
            embed.add_field(name="Score %", value=hero_stats["Score %"], inline=True)
            embed.add_field(name="Cards", value=hero_stats["Cards"], inline=True)
            embed.add_field(name="Cards +/-", value=hero_stats["Cards +/-"], inline=True)
            embed.add_field(name="Floor", value=hero_stats["Floor"], inline=True)
            embed.add_field(name="Floor %", value=hero_stats["Floor %"], inline=True)
            embed.add_field(name="Followers", value=hero_stats["Followers"], inline=True)
            embed.add_field(name="Views", value=hero_stats["Views"], inline=True)

            image_path = hero_stats["IMG"]
            file = discord.File(image_path, filename=os.path.basename(image_path))
            embed.set_image(url=f"attachment://{os.path.basename(image_path)}")

            await message.channel.send(embed=embed, file=file)
        else:
            await message.channel.send("Hero not found.")

# Run the Discord bot (replace 'YOUR_BOT_TOKEN' with your bot token)
client.run('')
