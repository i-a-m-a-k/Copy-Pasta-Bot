DB_NAME             = './db/mysqlite.db'
ROASTS_NAME         = 'roasts.txt'

KEY_EXISTS          = 'Key already exists in database.'
KEY_EXISTS_ADD      = 'Could not add because this key already exists. Use `add_o` to overwrite.'
KEY_EXISTS_RENAME   = 'Could not rename because this key already exists. Use `rename_o` to overwrite.'
KEY_EXISTS_STEAL    = 'Could not steal because this key already exists. Provide new key name as well.'
KEY_NOT_FOUND       = 'Key you specified does not exist.'

SUCCESSFUL          = 'Success!'
UNSUCCESSFUL        = 'Something went wrong :/'

REPLY_TO_MESSAGE    = 'You need to reply to a message to use this command.'

WRONG_ARGS          = 'You are using the command wrong. Please check `;;help`'
WRONG_ARGS_ADD      = '`add <key> <value>` or `add <key>` and reply to a message or add <key> and add an attachment'
WRONG_ARGS_RENAME   = '`rename <old_key> <new_key>` or `rename_o <old_key> <new_key>`'
WRONG_ARGS_DEL      = '`delete <key>`'
WRONG_ARGS_STEAL    = 'Sorry, we do not encourage human trafficking. Please mention a key to steal.'

WRONG_USER_ID       = 'The user you tagged is either in the wrong position or wrongly formatted.'

EMPTY_LIST          = 'You have not saved any text yet.'
EMPTY_LIST_STEAL    = 'The user has not saved any text yet.'
EMPTY_MESSAGE       = 'The message you replied to seems to be empty.'

BLACKLISTED         = 'You have been blacklisted from using the bot.'
NOT_BLACKLISTED     = 'User is not blacklisted.'
BLACKLIST_NO_FOUL   = 'You cannot blacklist another admin.'
BLACKLISTED_AlREADY = 'User is already blacklisted.'
BLACKLIST_EMPTY     = 'No users have been blacklisted :)'
BLACKLIST_SUCCESS   = 'Successfully blacklisted '
UNBLACKLIST_SUCCESS = 'Successfully unblacklisted '
ADMIN_ONLY          = 'This is an admin only command.'


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
- **forbesify** : Convert text to...
- **stretch** : Streeeeech aaaaa teeeext
- **roast <@user>** : Roast a user (No need to reply to message)
- **flirt <@user>** : Flirt with a user (No need to reply to message)
- **dream <prompt>** :  Generate an image from Luma AI. (No need to reply to message). _The prompt and the generated image might be logged by Luma AI. The prompt and the generated image with user id are definitely logged by the bot for moderation purposes_
'''

SAVED_MSGS = 'Saved messages for:'

# REGEX
COMMAND 		= r'^;;.' # commands preceded by ;;
# REPLACE 		= r'(^|\S+\s+);;\S+;;(\s+\S+|$)' # ;;word;;
REPLACE			= r';;\S+;;'

COMMAND_COOLDOWN = 2  # Cooldown of 2 seconds
ADMIN_COMMANDS = ['blacklist', 'roast_add']
