import os

DB_NAME             = './db/mysqlite.db'
ASSETS_DIR          = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
KEY_EXISTS_ADD      = 'Could not add because this key already exists. Use `add_o` to overwrite.'
SUCCESSFUL          = 'Success!'
WRONG_USER_ID       = 'The user you tagged is either in the wrong position or wrongly formatted.'
EMPTY_MESSAGE       = 'The message you replied to seems to be empty.'
REGEX_USAGE         = 'Usage: `;;s <pattern> <replacement> [flags g, i, count]`'
REGEX_NO_REPLY      = 'Please reply to a message to use this command.\n' + REGEX_USAGE
REGEX_EMPTY_MSG     = 'Cannot regex an empty message or a message with only attachments.\n' + REGEX_USAGE
REGEX_NOT_FOUND     = 'No matching pattern found.'

# REGEX
COMMAND 		= r'^;;\S' # commands preceded by ;; with no whitespace after
REPLACE			= r';;\S+;;'

# Key and Value Length Limits
MAX_KEY_LENGTH = 64
MAX_VALUE_LENGTH = 2000
KEY_TOO_LONG = f'Key name cannot exceed {MAX_KEY_LENGTH} characters.'
VALUE_TOO_LONG = f'Key value cannot exceed {MAX_VALUE_LENGTH} characters.'

# Per-User Key Limits
MAX_KEYS_PER_USER = 1000
KEY_LIMIT_REACHED = f'You have reached the maximum limit of {MAX_KEYS_PER_USER} saved keys. Please delete some keys using `;;delete <key>` before adding new ones.'

# Set of Blacklisted user IDs (O(1) lookups)
BLACKLIST: set[int] = set()

# Cooldown Durations (seconds)
DEFAULT_COOLDOWN = 10.0      # 10 seconds for all general commands
DREAM_COOLDOWN = 60.0        # 60 seconds (1 minute) for dream generation

AUTO_DELETE_DELAY = 60  # Auto-delete embeds/status responses after 60 seconds (1 minute)

# Dream Moderation & Logs
DREAM_BANNED_FILE   = 'db/dream_banned_users.csv'
DREAM_UNBANNED_FILE = 'db/dream_manually_unbanned_users.csv'
DREAM_LOGS_FILE     = 'db/dream_logs.csv'

