from typing import Callable, Union, Optional
import discord
import constants
import do_not_push
from cmds import *  # noqa: F403
from DatabaseManager import DatabaseManager
from Message import Message

def is_admin(user_id: int):
    return user_id in do_not_push.ADMINS

class CommandHandler:
    def __init__(self, db_manager: DatabaseManager, get_bot: Callable):
        self.db = db_manager

        self.commands = {
            "help": lambda message: help.help(message.args),

            # Copypasta
            "add": lambda message: add.add(message, self.db, overwrite=False),
            "add_o": lambda message: add.add(message, self.db, overwrite=True),
			"saved": lambda message: saved.handle_saved(message, self.db),
            "delete": lambda message: delete.delete(message, self.db),
            "delete_me": lambda message: delete_me.delete_me(
                self.db, message.author.id
            ),
            "rename": lambda message: rename_key.handle_rename(
                message, self.db, overwrite=False
            ),
            "rename_o": lambda message: rename_key.handle_rename(
                message, self.db, overwrite=True
            ),
            "steal": lambda message: steal.handle_steal(
                self.db, message.author, message.args
            ),
            "random": lambda message: random_key.handle_random(
                message.author, message.args, self.db
            ),
            "search": lambda message: search.handle_search(
                self.db, message.author, message.args
            ),

            # Text transform
            "clap": lambda message: text_transform.handle_text_transform(
                "clap", message
            ),
            "zalgo": lambda message: text_transform.handle_text_transform(
                "zalgo", message
            ),
            "forbesify": lambda message: text_transform.handle_text_transform(
                "forbesify", message
            ),
            "copypasta": lambda message: text_transform.handle_text_transform(
                "copypasta", message
            ),
            "owo": lambda message: text_transform.handle_text_transform("owo", message),
            "uwu": lambda message: text_transform.handle_text_transform(
                "owo", message
            ),  # Alias
            "stretch": lambda message: text_transform.handle_text_transform(
                "stretch", message
            ),

            # Fun
            "mock": mock.handle_mock,
            "roast": lambda message: roast.roast(message.message_obj, self.get_bot()),
            "roast_add": lambda message: roast.add_roast(message),

            # TODO
            "deepfry": lambda message: deepfry.handle_deepfry_command(
                message.reference
            ),

            # 'dream': lambda message: self._handle_dream(message.author, message.args, message.reference),
            "dream": lambda message: dream.handle_dream_command(message.reference),

            # Admin
			# TODO: BLACKLIST
            "blacklist": lambda message: blacklist.handle_blacklist(
                message.author.id, message.args
            ),
        }
        self.get_bot = get_bot

	# TODO: BLACKLIST
    def _handle_blacklist_remove(self, user: discord.User, args: list) -> str:
        if not is_admin(user.id):
            return "You don't have permission to use this command."
        if len(args) != 2 or not args[1].startswith("<@") or not args[1].endswith(">"):
            return "Invalid user mention"
        user_id_to_remove = int(args[1][2:-1])
        if user_id_to_remove not in do_not_push.BLACKLIST:
            return "User is not blacklisted."
        do_not_push.BLACKLIST.remove(user_id_to_remove)
        return f"User <@{user_id_to_remove}> has been removed from the blacklist."

    async def handle_command(
        self, message: Message
    ) -> Optional[Union[str, discord.File]]:
        args = message.args
        if not args:
            return None

        command = args[0]
        if command in self.commands:
            if command in constants.ADMIN_COMMANDS:
                if not is_admin(message.author.id):
                    return constants.ADMIN_ONLY
                return self.commands[command](message)

            if command in ["dream", "deepfry"]:
                return await self.commands[command](message)
            else:
                return self.commands[command](message)
        return None
