DB_NAME             = './db/mysqlite.db'
KEY_EXISTS_ADD      = 'Could not add because this key already exists. Use `add_o` to overwrite.'
KEY_EXISTS_RENAME   = 'Could not rename because this key already exists. Use `rename_o` to overwrite.'
KEY_EXISTS_STEAL    = 'Could not steal because this key already exists. Provide new key name as well.'
KEY_NOT_FOUND       = 'Key you specified does not exist.'
SUCCESSFUL          = 'Success!'
UNSUCCESSFUL        = 'Something went wrong :/'
WRONG_ARGS          = 'You are using the command wrong. Please check `;;help`'
WRONG_ARGS_ADD      = '`add <key> <value>` or `add <key>` and reply to a message'
WRONG_ARGS_DEL      = '`delete <key>`'
WRONG_USER_ID       = 'The user you tagged is either in the wrong position or wrongly formatted.'
EMPTY_LIST          = 'You have not saved any text yet.'
EMPTY_LIST_STEAL    = 'The user has not saved any text yet.'
EMPTY_MESSAGE       = 'The message you replied to seems to be empty.'
HELP_TEXT           = '''
Start command with `;;`
- **add <key> <message>** : Add text to db
- **add_o <key> <message>** : Add text but overwrite if exists
- **help** : This message
- **saved** : See all saved texts
- **delete <key>** : Delete text associated with this key
- **delete_me** : Delete all your keys (can't be undone)
- **rename <original_key> <new_key>** : Rename a key
- **rename_o <original_key> <new_key>** : Rename a key but overwrite
- **steal <user> <key> <new_key>**: Steal a key from the user. `new_key` is optional.

Usage ;;key;;

Meme Commands: (work only when you reply to a text or an image)
- **mock** : Mock a message
- **clap** : Clap between words
- **zalgo** : Add zalgo text effects
- **deepfry** : Deep fry an image
- **owo** : OwOify text
- **copypasta** : Generate copypasta text from a message
- **forbesify** : Convert text to...
- **stretch** : Streeeeech aaaaa teeeext

Usage: ;;command
'''

# REGEX
COMMAND 		= r'^;;.' # commands preceded by ;;
REPLACE 		= r'(^|\S+\s+);;\S+;;(\s+\S+|$)' # ;;word;;

# List of Blacklisted users
BLACKLIST = []

COMMAND_COOLDOWN = 2  # Cooldown of 2 seconds