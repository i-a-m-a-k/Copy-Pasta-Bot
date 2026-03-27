DB_NAME             = './db/mysqlite.db'
KEY_EXISTS_ADD      = 'Could not add because this key already exists. Use `add_o` to overwrite.'
KEY_EXISTS_RENAME   = 'Could not rename because this key already exists. Use `rename_o` to overwrite.'
KEY_EXISTS_STEAL    = 'Could not steal because this key already exists. Provide new key name as well.'
KEY_NOT_FOUND       = 'Key you specified does not exist.'
SUCCESSFUL          = 'Success!'
UNSUCCESSFUL        = 'Something went wrong :/'
WRONG_ARGS          = 'You are using the command wrong. Please check `;;help`'
WRONG_ARGS_ADD      = '`add <key> <value>` or `add <key>` and reply to a message or add <key> and add an attachment'
WRONG_ARGS_DEL      = '`delete <key>`'
WRONG_ARGS_STEAL    = 'Sorry, we do not encourage human trafficking. Please mention a key to steal.'
WRONG_USER_ID       = 'The user you tagged is either in the wrong position or wrongly formatted.'
EMPTY_LIST          = 'You have not saved any text yet.'
EMPTY_LIST_STEAL    = 'The user has not saved any text yet.'
EMPTY_MESSAGE       = 'The message you replied to seems to be empty.'
REGEX_USAGE         = 'Usage: `;;s <pattern> <replacement> [flags g, i, count]`'
REGEX_NO_REPLY      = 'Please reply to a message to use this command.\n' + REGEX_USAGE
REGEX_EMPTY_MSG     = 'Cannot regex an empty message or a message with only attachments.\n' + REGEX_USAGE
REGEX_NOT_FOUND     = 'No matching pattern found.'
HELP_TEXT           = '''
**Basic Usage**:
`;;cmd` - to interact with the bot (modify keys, meme commands)
`;;key;;` - to recall keys

Save keys using `;;add <key> <value>` or `;;add <key>` and reply to a message/add attachment
For detailed help try `;;help copypasta` or `;;help memes`
'''

HELP_TEXT_CP       = '''
**Copypasta Commands:**
- **add <key> <message>** : Add text to db. You can also reply to a message or attach some media instead of <message>.
- **add_o <key> <message>** : Add text but overwrite if exists
- **help** : This message
- **saved** : See all saved texts
- **delete <key>** : Delete text associated with this key
- **delete_me** : Delete all your keys (can't be undone)
- **rename <original_key> <new_key>** : Rename a key
- **rename_o <original_key> <new_key>** : Rename a key but overwrite
- **steal <user> <key> <new_key>**: Steal a key from the user. `new_key` is optional.
- **random <term>** : `term` is optional. Send a random value from saved keys. If term is provided, it filters out keys without term in them.
- **search** <key> : Search your keys for occurence of this key
'''

HELP_TEXT_MEMES    = '''
**Meme Commands:** (Reply to a message)
- **mock** : Mock a message
- **clap** : Clap between words
- **zalgo** : Add zalgo text effects
- **deepfry** : Deep fry an image
- **owo** : OwOify text
- **copypasta** : Generate copypasta text from a message
- **stretch** : Streeeeech aaaaa teeeext
- **vaporwave** : Ｃｏｎｖｅｒｔ　ｔｅｘｔ　ｔｏ　ｆｕｌｌｗｉｄｔｈ
- **emojify** : Convert text to 🇪 🇲 🇴 🇯 🇮 🇸
- **roast <@user>** : Roast a user (No need to reply to message)
- **flirt <@user>** : Flirt with a user (No need to reply to message)
- **s <pattern> <replacement> [flags g, i, count]**: Vim-like regex, replaces `pattern` in replied message with `replacement` (text only)
- **dream** : Create an image or a video from a text prompt or an image. (No need to reply to message)
'''

SAVED_MSGS = 'Saved messages for:'

# REGEX
COMMAND 		= r'^;;.' # commands preceded by ;;
# REPLACE 		= r'(^|\S+\s+);;\S+;;(\s+\S+|$)' # ;;word;;
REPLACE			= r';;\S+;;'

# List of Blacklisted users
BLACKLIST = []

COMMAND_COOLDOWN = 2  # Cooldown of 2 seconds
