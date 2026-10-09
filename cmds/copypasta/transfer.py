import io
import json
from datetime import datetime, timezone
from typing import Optional, Union
import discord
import constants
from core.database import DatabaseManager
from ui.embeds import success_embed, error_embed, warning_embed, info_embed
from ui.confirmation import ImportConfirmView

MAX_IMPORT_FILE_SIZE = 1_048_576  # 1 MB
MAX_IMPORT_KEYS = 1000
MAX_KEY_LENGTH = constants.MAX_KEY_LENGTH
MAX_VALUE_LENGTH = constants.MAX_VALUE_LENGTH

def _format_size(size_bytes: int) -> str:
	if size_bytes >= 1_048_576:
		return f"{size_bytes / 1_048_576:.1f} MB"
	elif size_bytes >= 1024:
		return f"{size_bytes / 1024:.1f} KB"
	return f"{size_bytes} bytes"

async def handle_export(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference] = None,
	message: Optional[discord.Message] = None
) -> Union[discord.Embed, dict]:
	"""
	Exports all of a user's saved keys to a clean JSON file and delivers it via Direct Message (DM).
	If the user's DMs are closed, warns them in the channel to enable DMs.
	"""
	_, user_db = db_manager._get_user_entry(user.id)
	if not user_db:
		return info_embed("You don't have any saved keys to export.")

	export_payload = {
		"version": 1,
		"user_id": user.id,
		"exported_at": datetime.now(timezone.utc).isoformat(),
		"keys_count": len(user_db),
		"keys": dict(user_db)
	}

	json_bytes = json.dumps(export_payload, indent=2, ensure_ascii=False).encode('utf-8')
	buffer = io.BytesIO(json_bytes)
	user_name = getattr(user, 'name', 'user')
	discord_file = discord.File(buffer, filename=f"copypasta_keys_{user_name}.json")

	dm_embed = success_embed(
		f"Here is your backup of **{len(user_db)}** saved key(s)!",
		title="📦 Keys Exported"
	)

	# If invoked inside a guild channel, deliver via DM to preserve privacy
	if message and message.guild is not None:
		try:
			await user.send(embed=dm_embed, file=discord_file)
			return success_embed(
				"Your saved keys have been exported and sent to your Direct Messages (DMs)!",
				title="📬 Export Sent"
			)
		except discord.Forbidden:
			return warning_embed(
				"Could not send your export file via Direct Message. Please enable DMs from server members in your Discord Privacy Settings and try again.",
				title="🔒 DMs Disabled"
			)
		except Exception as e:
			return error_embed(f"Failed to send DM: {e}")
	else:
		# Already invoked inside DMs
		return {
			"embed": dm_embed,
			"file": discord_file
		}

async def handle_import(
	db_manager: DatabaseManager,
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference] = None,
	message: Optional[discord.Message] = None
) -> Union[discord.Embed, dict]:
	"""
	Imports saved keys from an attached or replied JSON file with strict security validation.
	Enforces DM-only execution, payload limits, and interactive confirmation for key overwrites.
	"""
	# 1. Enforce DM-Only Execution for privacy and security
	if message and message.guild is not None:
		return warning_embed(
			"For your privacy, the `;;import` command can only be used in Direct Messages (DMs). Please send your JSON file to me here in DMs!",
			title="🔒 DM Only Command"
		)

	# 2. Retrieve JSON Attachment from message or reply
	attachment = None
	if message and message.attachments:
		attachment = message.attachments[0]
	elif reply and hasattr(reply, 'resolved') and reply.resolved and getattr(reply.resolved, 'attachments', None):
		attachment = reply.resolved.attachments[0]

	if not attachment:
		return warning_embed(
			"Please attach a JSON file or reply to a message containing a JSON file with `;;import`.",
			title="⚠️ No JSON File Found"
		)

	# 3. File Size Validation (before downloading)
	if getattr(attachment, 'size', 0) > MAX_IMPORT_FILE_SIZE:
		return error_embed(
			f"File size ({_format_size(attachment.size)}) exceeds the 1 MB limit. Import rejected for safety.",
			title="❌ File Too Large"
		)

	# 4. File Extension / Content Type Validation
	filename = getattr(attachment, 'filename', '').lower()
	if not filename.endswith('.json'):
		return error_embed(
			"The uploaded attachment must be a `.json` file.",
			title="❌ Invalid File Format"
		)

	# 5. Download and UTF-8 Decode
	try:
		raw_bytes = await attachment.read()
	except Exception as e:
		return error_embed(f"Failed to read file attachment: {e}")

	if len(raw_bytes) > MAX_IMPORT_FILE_SIZE:
		return error_embed("File size exceeds 1 MB limit.", title="❌ File Too Large")

	try:
		text = raw_bytes.decode('utf-8')
	except UnicodeDecodeError:
		return error_embed(
			"The file content is not valid UTF-8 text.",
			title="❌ Encoding Error"
		)

	# 6. JSON Syntax Parsing
	try:
		data = json.loads(text)
	except json.JSONDecodeError as e:
		return error_embed(
			f"Failed to parse JSON file: `{e}`",
			title="❌ Malformed JSON"
		)

	# 7. Root Object Structure Validation (reject arrays, primitives, nested bombs)
	if not isinstance(data, dict):
		return error_embed(
			"Invalid JSON structure. Root element must be a JSON object (`{ ... }`).",
			title="❌ Invalid Structure"
		)

	# 8. Schema Resolution: structured export wrapper vs direct dictionary
	if "keys" in data and isinstance(data["keys"], dict):
		raw_keys = data["keys"]
	else:
		raw_keys = data

	if not raw_keys:
		return warning_embed("The JSON file contains no keys to import.", title="⚠️ Empty File")

	if len(raw_keys) > MAX_IMPORT_KEYS:
		return error_embed(
			f"The JSON file contains {len(raw_keys)} keys, exceeding the maximum limit of {MAX_IMPORT_KEYS} keys per import.",
			title="❌ Key Limit Exceeded"
		)

	# 9. Strict Key & Value Validation
	validated_keys: dict[str, str] = {}
	for k, v in raw_keys.items():
		# Key must be string
		if not isinstance(k, str):
			return error_embed(f"Invalid key type `{type(k).__name__}`. All keys must be strings.", title="❌ Invalid Key Type")

		key_name = k.strip()
		if not key_name or len(key_name) > MAX_KEY_LENGTH:
			return error_embed(
				f"Key `{k[:20]}` length must be between 1 and {MAX_KEY_LENGTH} characters.",
				title="❌ Invalid Key Length"
			)

		if any(c.isspace() for c in key_name):
			return error_embed(
				f"Key `{key_name}` contains whitespace. Keys cannot contain spaces.",
				title="❌ Invalid Key Name"
			)

		if ';;' in key_name:
			return error_embed(
				f"Key `{key_name}` cannot contain `;;` tokens.",
				title="❌ Invalid Key Name"
			)

		# Reject control characters (0-31) or null bytes
		if any(ord(c) < 32 for c in key_name):
			return error_embed(
				f"Key `{key_name}` contains invalid control characters.",
				title="❌ Malicious Key Name"
			)

		# Value must be pure string
		if not isinstance(v, str):
			return error_embed(
				f"Key `{key_name}` contains a non-string value of type `{type(v).__name__}`. Nested arrays and objects are strictly prohibited.",
				title="❌ Invalid Value Type"
			)

		val_text = v.strip()
		if not val_text:
			return error_embed(
				f"Key `{key_name}` has an empty value.",
				title="❌ Empty Value"
			)

		if len(val_text) > MAX_VALUE_LENGTH:
			return error_embed(
				f"Value for key `{key_name}` exceeds the Discord limit of {MAX_VALUE_LENGTH} characters ({len(val_text)} chars).",
				title="❌ Value Too Long"
			)

		validated_keys[key_name] = val_text

	# 10. Overwrite Collision Detection & Hard Limit Enforcement
	current_keys = set(db_manager.get_user_keys(user.id))
	overlapping = [k for k in validated_keys if k in current_keys]
	new_keys = [k for k in validated_keys if k not in current_keys]

	if len(current_keys) + len(new_keys) > constants.MAX_KEYS_PER_USER:
		return error_embed(
			f"Importing these keys would exceed the limit of {constants.MAX_KEYS_PER_USER} saved keys per user. "
			f"You currently have {len(current_keys)} key(s), and this import would add {len(new_keys)} new key(s) "
			f"(total: {len(current_keys) + len(new_keys)}).",
			title="❌ Key Limit Exceeded"
		)

	# 11. Overwrite Confirmation with Interactive Buttons
	if overlapping:
		sample_overlapping = overlapping[:10]
		sample_str = ", ".join(f"`{k}`" for k in sample_overlapping)
		if len(overlapping) > 10:
			sample_str += f" and {len(overlapping) - 10} more..."

		embed = warning_embed(
			f"This import contains **{len(overlapping)}** key(s) that already exist in your saved keys and will be **overwritten**:\n"
			f"{sample_str}\n\n"
			f"• **Total to import**: {len(validated_keys)}\n"
			f"• **New keys**: {len(new_keys)}\n"
			f"• **Overwriting**: {len(overlapping)}\n\n"
			f"Are you sure you want to proceed?",
			title="⚠️ Overwrite Confirmation"
		)

		view = ImportConfirmView(
			user_id=user.id,
			keys_dict=validated_keys,
			overlapping_keys=overlapping,
			db_manager=db_manager
		)

		return {
			"embed": embed,
			"view": view
		}

	# 12. No Collisions: Direct Batch Import
	new_count, _ = db_manager.import_user_keys(user.id, validated_keys, overwrite=False)
	return success_embed(
		f"Successfully imported **{new_count}** new key(s) to your saved keys!",
		title="✅ Import Complete"
	)
