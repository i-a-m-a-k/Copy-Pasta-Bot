import os
import random
import discord
from utils.Message import Message

def get_asset_path(filename: str) -> str:
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root_dir, 'assets', filename)

def load_flirts() -> list:
    """Load flirts from the flirts.txt file"""
    try:
        with open(get_asset_path('flirts.txt'), 'r', encoding='utf-8') as file:
            flirts = [line.strip() for line in file if line.strip()]
        return flirts
    except FileNotFoundError:
        print("Error: flirts.txt file not found in assets directory")
        return ["Error: Couldn't find flirts file. Contact the bot owner."]
    except Exception as e:
        print(f"Error loading flirts: {e}")
        return ["Error: Couldn't load flirts. Contact the bot owner."]

def get_random_flirt() -> str:
    """Get a random flirt from the flirts file"""
    flirts = load_flirts()
    return random.choice(flirts)

def get_random_flirty_emoji() -> str:
    """Get a random flirty emoji"""
    flirty_emojis = [
        "😘", "😍", "💕", "❤️", "💖", "💓", "💗", "💞", "💘", "💝",
        "😉", "😏", "🥰", "💋", "✨", "🌹", "🔥", "👀", "😻", "❣️"
    ]
    return random.choice(flirty_emojis)

def handle_flirt_command(message: Message) -> str:
    """Handle the ;;flirt command and return the response message"""
    if not message.mentions:
        return "You need to mention someone to flirt! Try ;;flirt @username"
    target_user = message.mentions[0]
    flirt = get_random_flirt()
    emoji = get_random_flirty_emoji()
    response = f"{target_user.mention} {discord.utils.escape_markdown(flirt)} {emoji}"
    return response
