import os
import random
import discord
import constants

def get_asset_path(filename: str) -> str:
    return os.path.join(constants.ASSETS_DIR, filename)

# Module-level cache — loaded once on first use
_FLIRTS_CACHE = None

def load_flirts() -> list:
    """Load flirts from the flirts.txt file (cached after first call)."""
    global _FLIRTS_CACHE
    if _FLIRTS_CACHE is not None:
        return _FLIRTS_CACHE
    try:
        with open(get_asset_path('flirts.txt'), 'r', encoding='utf-8') as file:
            _FLIRTS_CACHE = [line.strip() for line in file if line.strip()]
        return _FLIRTS_CACHE
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

def handle_flirt_command(message: discord.Message) -> str:
    """Handle the ;;flirt command and return the response message"""
    if not message.mentions:
        return "You need to mention someone to flirt! Try ;;flirt @username"
    
    target_user = message.mentions[0]
    flirt = get_random_flirt()
    emoji = get_random_flirty_emoji()
    response = f"{target_user.mention} {discord.utils.escape_markdown(flirt)} {emoji}"
    return response
