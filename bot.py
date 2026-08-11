import os
import sys
import do_not_push
from core.bot_client import DiscordBot

# Ensure workspace root is on Python module search path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
	"""Main entry point for CopyPastaBot."""
	bot = DiscordBot(do_not_push.API_TOKEN)
	bot.run()

if __name__ == '__main__':
	main()