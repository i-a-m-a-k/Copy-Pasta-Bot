import os
import random
import discord

def get_asset_path(filename: str) -> str:
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root_dir, 'assets', filename)

# Module-level cache — loaded once on first use
_FLIRTS_CACHE = None

def load_flirts() -> list:
    """Load flirts from the flirts.txt file (cached after first call)."""
    global _FLIRTS_CACHE
    if _FLIRTS_CACHE is not None:
        return _FLIRTS_CACHE
    try:
        with open(get_asset_path('flirts.txt'), 'r', encoding='utf-8') as file:
            # Filter out empty lines
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
    # Check if there's a user mention in the message
    if not message.mentions:
        return "You need to mention someone to flirt! Try ;;flirt @username"
    
    # Get the first mentioned user
    target_user = message.mentions[0]
    
    # Get a random flirt
    flirt = get_random_flirt()
    
    # Get a random flirty emoji
    emoji = get_random_flirty_emoji()
    
    # Format the response with the target user mention, flirt, and emoji
    # Using discord.utils.escape_markdown to preserve '*' for censoring
    response = f"{target_user.mention} {discord.utils.escape_markdown(flirt)} {emoji}"
    
    return response