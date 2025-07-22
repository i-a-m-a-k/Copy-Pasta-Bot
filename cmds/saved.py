import discord
import constants
import do_not_push
from DatabaseManager import DatabaseManager
from Message import Message

def is_admin(user_id: int):
    return user_id in do_not_push.ADMINS

def handle_saved(message: Message, db: DatabaseManager) -> str:
        args = message.args
        if len(args) == 2 and args[1].startswith("<@") and args[1].endswith(">"):
            if not is_admin(message.author.id):
                return "You don't have permission to view another user's keys."
            find_keys_for = args[1][2:-1]
            # keys = sorted(self.db.get_user_keys(mentioned_user_id))
            # return f"Keys for <@{mentioned_user_id}>:\n- " + '\n- '.join(keys) if keys else constants.EMPTY_LIST
        else:
            find_keys_for = message.author.id

        keys = sorted(db.get_user_keys(find_keys_for))
        if len(keys) == 0:
            return constants.EMPTY_LIST

        return_text = (
            f"{constants.SAVED_MSGS} <@{str(find_keys_for)}>\n"
            + "- "
            + "\n- ".join(keys)
            if keys
            else constants.EMPTY_LIST
        )

        message_obj = message.message_obj
        if isinstance(message_obj.channel, discord.TextChannel) or isinstance(
            message_obj.channel, discord.VoiceChannel
        ):
            if (
                message_obj.channel.permissions_for(
                    message_obj.channel.guild.me
                ).add_reactions
                and message_obj.channel.permissions_for(
                    message_obj.channel.guild.me
                ).manage_messages
            ):
                return_text = (
                    f"{constants.SAVED_MSGS} <@{str(find_keys_for)}>\n1/{str(len(keys) // 10 + 1)}\n"
                    + "- "
                    + "\n- ".join(keys[:10])
                    if keys
                    else constants.EMPTY_LIST
                )

        return return_text
