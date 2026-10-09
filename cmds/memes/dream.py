import io
import asyncio
from typing import Optional, Union, Callable
import aiohttp
try:
	from lumaai import AsyncLumaAI
except ImportError:
	AsyncLumaAI = None
from lumaai import LumaAI

import discord
import constants
import do_not_push
import time
import argparse
import shlex
import os
import csv
from datetime import datetime
from ui import (
	error_embed,
	warning_embed,
	get_http_session,
	extract_image_url
)

# Content moderation configuration
MODERATION_THRESHOLDS = {
	"sexual/minors": 0.20,
	"self-harm": 0.50,
	"self-harm/intent": 0.50,
	"self-harm/instructions": 0.50,
	"hate/threatening": 0.50,
	"harassment/threatening": 0.50,
	"violence/graphic": 0.70,
	"hate": 0.80,
	"sexual": 0.85,
	"harassment": 0.90,
	"violence": 0.90,
	"illicit/violent": 0.70,
	"illicit": 0.85,
}

# Severe zero-tolerance categories that trigger an immediate command ban
SEVERE_BAN_CATEGORIES = {
	"sexual/minors",
	"self-harm",
	"self-harm/intent",
	"self-harm/instructions",
}

pending_logs = {}

def log_dream_command(user_id, username, prompt, generation_type, media_url=None, status="success"):
	log_file = constants.DREAM_LOGS_FILE
	timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

	if not media_url:
		pending_logs[user_id] = (timestamp, user_id, username, prompt, generation_type, None, status)
		return

	if user_id in pending_logs:
		del pending_logs[user_id]

	os.makedirs(os.path.dirname(log_file), exist_ok=True)
	file_exists = os.path.isfile(log_file)

	with open(log_file, 'a', newline='', encoding='utf-8') as f:
		writer = csv.writer(f)
		if not file_exists:
			writer.writerow(['timestamp', 'user_id', 'username', 'prompt', 'generation_type', 'media_url', 'status'])
		writer.writerow([timestamp, user_id, username, prompt, generation_type, media_url, status])

def add_banned_user(user_id: Union[int, str], username: str, prompt: str) -> None:
	banned_file = constants.DREAM_BANNED_FILE
	os.makedirs(os.path.dirname(banned_file), exist_ok=True)
	file_exists = os.path.isfile(banned_file)
	timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

	with open(banned_file, 'a', newline='', encoding='utf-8') as f:
		writer = csv.writer(f)
		if not file_exists or os.path.getsize(banned_file) == 0:
			writer.writerow(['timestamp', 'user_id', 'username', 'banned_prompt'])
		writer.writerow([timestamp, str(user_id), username, prompt])

def is_user_banned(user_id: Union[int, str]) -> bool:
	banned_file = constants.DREAM_BANNED_FILE
	if not os.path.isfile(banned_file):
		return False
	try:
		with open(banned_file, 'r', newline='', encoding='utf-8') as f:
			reader = csv.DictReader(f)
			for row in reader:
				if row.get('user_id') and str(row['user_id']).strip() == str(user_id).strip():
					return True
	except Exception as e:
		print(f"Error checking dream ban: {e}")
	return False

def remove_banned_user(user_id: Union[int, str]) -> list[dict]:
	banned_file = constants.DREAM_BANNED_FILE
	unbanned_file = constants.DREAM_UNBANNED_FILE
	if not os.path.isfile(banned_file):
		return []

	remaining_rows = []
	removed_rows = []

	try:
		with open(banned_file, 'r', newline='', encoding='utf-8') as f:
			reader = csv.DictReader(f)
			fieldnames = reader.fieldnames or ['timestamp', 'user_id', 'username', 'banned_prompt']
			for row in reader:
				if str(row.get('user_id', '')).strip() == str(user_id).strip():
					removed_rows.append(row)
				else:
					remaining_rows.append(row)
	except Exception as e:
		print(f"Error reading dream banned file: {e}")
		return []

	if not removed_rows:
		return []

	try:
		with open(banned_file, 'w', newline='', encoding='utf-8') as f:
			writer = csv.DictWriter(f, fieldnames=fieldnames)
			writer.writeheader()
			writer.writerows(remaining_rows)
	except Exception as e:
		print(f"Error updating dream banned file: {e}")
		return []

	try:
		os.makedirs(os.path.dirname(unbanned_file), exist_ok=True)
		unbanned_exists = os.path.isfile(unbanned_file) and os.path.getsize(unbanned_file) > 0
		with open(unbanned_file, 'a', newline='', encoding='utf-8') as f:
			writer = csv.writer(f)
			if not unbanned_exists:
				writer.writerow(['timestamp', 'user_id', 'username', 'banned_prompt'])
			for row in removed_rows:
				writer.writerow([
					row.get('timestamp', ''),
					row.get('user_id', ''),
					row.get('username', ''),
					row.get('banned_prompt', '')
				])
	except Exception as e:
		print(f"Error writing to dream unbanned file: {e}")

	return removed_rows

def get_banned_users() -> list[dict]:
	banned_file = constants.DREAM_BANNED_FILE
	if not os.path.isfile(banned_file):
		return []
	try:
		with open(banned_file, 'r', newline='', encoding='utf-8') as f:
			reader = csv.DictReader(f)
			return [row for row in reader if row.get('user_id')]
	except Exception as e:
		print(f"Error reading dream ban list: {e}")
		return []


async def handle_dream_command(user, args, message=None):
	try:
		user_id = user.id
		is_admin = user_id in getattr(do_not_push, 'LUMA_USERS', []) or user_id in getattr(do_not_push, 'ADMINS', [])

		if not is_admin and await asyncio.to_thread(is_user_banned, user_id):
			return error_embed("You are not allowed to use the dream command.", title="🚫 Access Denied")
		
		# Parse the command arguments
		parser = argparse.ArgumentParser(add_help=False)
		parser.add_argument('-v', '--video', action='store_true', help='Generate a video instead of an image')
		parser.add_argument('-i2v', '--image-to-video', action='store_true', help='Transform an image into a video')
		parser.add_argument('-iref', '--image-ref', action='store_true', help='Use replied image as an image reference')
		parser.add_argument('-sref', '--style-ref', action='store_true', help='Use replied image as a style reference')
		parser.add_argument('-cref', '--character-ref', action='store_true', help='Use replied image as a character reference')
		parser.add_argument('-modify', '--modify-image', action='store_true', help='Modify the replied image')
		parser.add_argument('-w', '--weight', type=float, default=None, help='Weight of the image reference (0.0 to 1.0)')
		parser.add_argument('prompt', nargs='*', help='The prompt for generation')
		
		# Convert args to a string and use shlex to handle quoting
		args_string = " ".join(args[1:]) if args and args[0].lower() == "dream" else " ".join(args)
		try:
			parsed_args = parser.parse_args(shlex.split(args_string))
			is_video = parsed_args.video
			is_image_to_video = parsed_args.image_to_video
			has_iref = parsed_args.image_ref
			has_sref = parsed_args.style_ref
			has_cref = parsed_args.character_ref
			has_modify = parsed_args.modify_image
			weight_val = parsed_args.weight
			prompt = " ".join(parsed_args.prompt)
		except Exception:
			# Fallback for simpler parsing if argparse fails
			is_video = "-v" in args_string or "--video" in args_string
			is_image_to_video = "-i2v" in args_string or "--image-to-video" in args_string
			has_iref = "-iref" in args_string or "--image-ref" in args_string
			has_sref = "-sref" in args_string or "--style-ref" in args_string
			has_cref = "-cref" in args_string or "--character-ref" in args_string
			has_modify = "-modify" in args_string or "--modify-image" in args_string
			
			# Fallback parsing for weight
			weight_val = None
			if "-w" in args_string or "--weight" in args_string:
				parts = args_string.split()
				for i, p in enumerate(parts):
					if p in ["-w", "--weight"] and i + 1 < len(parts):
						try:
							weight_val = float(parts[i+1])
						except ValueError:
							pass
						break
			
			# Remove the flags from the prompt
			prompt = args_string
			for flag in ["-v", "--video", "-i2v", "--image-to-video", "-iref", "--image-ref", "-sref", "--style-ref", "-cref", "--character-ref", "-modify", "--modify-image"]:
				prompt = prompt.replace(flag, "")
			if weight_val is not None:
				weight_str = f"-w {weight_val}" if f"-w {weight_val}" in prompt else (f"--weight {weight_val}" if f"--weight {weight_val}" in prompt else "")
				if weight_str:
					prompt = prompt.replace(weight_str, "")

				prompt = prompt.replace("-w", "").replace("--weight", "")

			prompt = prompt.strip()
		
		# Determine current generation type - combine video and image-to-video into "video"
		requires_replied_image = is_image_to_video or has_iref or has_sref or has_cref or has_modify
		
		image_url = None
		if requires_replied_image:
			if not message:
				return warning_embed("This generation type requires you to reply to a message containing an image.", title="⚠️ Image Required")

			image_url = extract_image_url(reply=message)
			if not image_url:
				return warning_embed("The message you replied to doesn't contain any valid images.", title="⚠️ Image Not Found")
		
		num_advanced_flags = sum([has_iref, has_sref, has_cref, has_modify])
		if num_advanced_flags > 1:
			return warning_embed("Please use only one advanced image reference flag at a time (`-iref`, `-sref`, `-cref`, or `-modify`).", title="⚠️ Conflicting Flags")
		
		# Allow prompt to be empty ONLY if we are doing modify or image_to_video
		if not prompt and not is_image_to_video and not has_modify:
			embed = discord.Embed(
				title="Dream Command Usage",
				description="Generate AI images and videos using Luma AI.",
				color=discord.Color.blurple()
			)
			embed.add_field(
				name="Basic Usage",
				value="• `;;dream <prompt>` : Generate an image\n• `;;dream -v <prompt>` : Generate a 5s video",
				inline=False
			)
			if is_admin:
				embed.add_field(
					name="Advanced Options (Admins)",
					value=(
						"• **`-v`** : Video generation\n"
						"• **`-i2v`** : Transform replied image to video\n"
						"• **`-iref`** : Use replied image as reference (`-w <0.0-1.0>` for weight)\n"
						"• **`-sref`** : Use replied image as style reference\n"
						"• **`-cref`** : Use replied image as character reference\n"
						"• **`-modify`** : Modify replied image with prompt"
					),
					inline=False
				)
			return embed
		
		# Check content moderation
		if prompt:
			openai_key = getattr(do_not_push, "OPENAI_API_KEY", "")
			if openai_key:
				try:
					session = await get_http_session()
					async with session.post(
						"https://api.openai.com/v1/moderations",
						headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
						json={"input": prompt},
						timeout=aiohttp.ClientTimeout(total=5)
					) as mod_response:
						if mod_response.status == 200:
							mod_data = await mod_response.json()
							scores = mod_data.get("results", [{}])[0].get("category_scores", {})
							flagged_categories = [
								cat for cat, score in scores.items()
								if score >= MODERATION_THRESHOLDS.get(cat, 0.85)
							]

							if flagged_categories:
								is_severe = any(cat in SEVERE_BAN_CATEGORIES for cat in flagged_categories)
								if not is_admin:
									if is_severe:
										await asyncio.to_thread(
											add_banned_user,
											user_id=user.id,
											username=user.name if hasattr(user, 'name') else str(user),
											prompt=prompt
										)
										return error_embed(
											"Your prompt was flagged for a severe safety violation. You have been banned from using the dream command.",
											title="🚫 Moderation Violation"
										)
									return error_embed(
										"Your prompt was flagged by our safety filter for inappropriate content. Generation cancelled.",
										title="⚠️ Prompt Flagged"
									)
								return warning_embed("Your prompt was flagged by the safety system for inappropriate content.", title="⚠️ Safety Warning")
				except Exception as e:
					print(f"Moderation API error: {e}")

		# Initialize Luma AI client with auth_token
		if AsyncLumaAI is not None:
			client = AsyncLumaAI(auth_token=do_not_push.LUMA_API_KEY)
			is_async_client = True
		else:
			client = LumaAI(auth_token=do_not_push.LUMA_API_KEY)
			is_async_client = False
		
		# Get specific generation type for display purposes
		display_generation_type = "image-to-video" if is_image_to_video else ("video" if is_video else "image")

		await asyncio.to_thread(
			log_dream_command,
			user_id=user.id,
			username=user.name if hasattr(user, 'name') else str(user),
			prompt=prompt,
			generation_type=display_generation_type,
			media_url=None
		)
		
		# Create the generation request based on type
		if is_image_to_video:
			create_kwargs = {
				"prompt": prompt if prompt else "Transform this image into a cinematic video",
				"model": "ray-2",
				"keyframes": {
					"frame0": {
						"type": "image",
						"url": image_url
					}
				},
				"resolution": "540p",
				"duration": "5s"
			}
			if is_async_client:
				generation = await client.generations.create(**create_kwargs)
			else:
				generation = await asyncio.to_thread(client.generations.create, **create_kwargs)

		elif is_video:
			create_kwargs = {
				"prompt": prompt,
				"model": "ray-2",
				"resolution": "540p",
				"duration": "5s"
			}
			if is_async_client:
				generation = await client.generations.video.create(**create_kwargs)
			else:
				generation = await asyncio.to_thread(client.generations.video.create, **create_kwargs)
		else:
			kwargs = {
				"prompt": prompt,
				"model": "photon-1"
			}
			
			if image_url:
				safe_weight = None
				if weight_val is not None:
					safe_weight = max(0.0, min(1.0, weight_val))
					
				ref_dict = {"url": image_url}
				if safe_weight is not None:
					ref_dict["weight"] = safe_weight
					
				if has_iref:
					kwargs["image_ref"] = [ref_dict]
				elif has_sref:
					kwargs["style_ref"] = [ref_dict]
				elif has_cref:
					kwargs["character_ref"] = {"identity0": {"images": [image_url]}}
				elif has_modify:
					kwargs["modify_image_ref"] = ref_dict
			
			if is_async_client:
				generation = await client.generations.image.create(**kwargs)
			else:
				generation = await asyncio.to_thread(client.generations.image.create, **kwargs)
		
		# Poll until completion
		completed = False
		polling_count = 0
		max_polling = 120
		
		while not completed and polling_count < max_polling:
			if is_async_client:
				generation = await client.generations.get(id=generation.id)
			else:
				generation = await asyncio.to_thread(client.generations.get, id=generation.id)
			
			if generation.state == "completed":
				completed = True
			elif generation.state == "failed":
				failure_reason = getattr(generation, 'failure_reason', 'Unknown reason')
				if "moderation" in failure_reason.lower() or "400" in failure_reason:
					if not is_admin:
						await asyncio.to_thread(
							add_banned_user,
							user_id=user.id,
							username=user.name if hasattr(user, 'name') else str(user),
							prompt=prompt
						)
						return error_embed("Your generation request violated content moderation policies. You have been banned from using the dream command.", title="🚫 Moderation Violation")
					return warning_embed(f"{display_generation_type.capitalize()} generation violated moderation policies: {failure_reason}", title="⚠️ Moderation Violation")
				
				await asyncio.to_thread(
					log_dream_command,
					user_id=user.id,
					username=user.name if hasattr(user, 'name') else str(user),
					prompt=prompt,
					generation_type=display_generation_type,
					media_url=None,
					status="fail: " + failure_reason
				)
				return error_embed(f"{display_generation_type.capitalize()} generation failed: {failure_reason}", title="❌ Generation Failed")
			
			polling_interval = 5 if (is_video or is_image_to_video) else 3
			await asyncio.sleep(polling_interval)
			polling_count += 1
			
		if not completed:
			await asyncio.to_thread(
				log_dream_command,
				user_id=user.id,
				username=user.name if hasattr(user, 'name') else str(user),
				prompt=prompt,
				generation_type=display_generation_type,
				media_url=None,
				status="fail: timeout"
			)
			return error_embed(f"{display_generation_type.capitalize()} generation timed out. Please try again later.", title="⏱️ Generation Timeout")
		
		# Get the media URL and appropriate file extension
		if is_video or is_image_to_video:
			media_url = generation.assets.video
			file_extension = "mp4"
			discord_filename = "dream_video_result.mp4"
		else:
			media_url = generation.assets.image
			file_extension = "jpg"
			discord_filename = "dream_result.jpg"

		await asyncio.to_thread(
			log_dream_command,
			user_id=user.id,
			username=user.name if hasattr(user, 'name') else str(user),
			prompt=prompt,
			generation_type=display_generation_type,
			media_url=media_url,
			status="success"
		)
		
		# Download the generated content directly into memory using shared aiohttp session
		session = await get_http_session()
		async with session.get(media_url) as media_response:
			if media_response.status != 200:
				return error_embed(f"Failed to download generated media: HTTP {media_response.status}")
			media_content = await media_response.read()

		buffer = io.BytesIO(media_content)
		buffer.seek(0)
		
		discord_file = discord.File(
			fp=buffer,
			filename=discord_filename,
			description=f"Dream {display_generation_type} completed for '{prompt}'"
		)
		
		return discord_file
		
	except Exception as e:
		error_message = str(e)
		await asyncio.to_thread(
			log_dream_command,
			user_id=user.id,
			username=user.name if hasattr(user, 'name') else str(user),
			prompt=prompt if 'prompt' in locals() else "unknown",
			generation_type=display_generation_type if 'display_generation_type' in locals() else "unknown",
			media_url=None,
			status=f"error: {error_message}"
		)
		return error_embed(f"Error generating content: {error_message}", title="❌ Generation Error")

async def handle_dream(
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference] = None,
	message: Optional[discord.Message] = None,
	get_client: Optional[Callable[[], Optional[discord.Client]]] = None
) -> Union[str, discord.File, discord.Embed, dict, None]:
	"""Handles the ;;dream Luma AI generation command and admin moderation flags (--ban, --unban, --banlist)."""
	cmd_args = args[1:] if args and args[0].lower() == "dream" else args
	if cmd_args:
		first_arg = cmd_args[0].lower()
		if first_arg in ("--ban", "-ban", "--unban", "-unban", "--banlist", "-banlist"):
			from core.config import is_admin as is_bot_admin
			if not is_bot_admin(user.id):
				return error_embed("You don't have permission to use this command.")

			from cmds.admin.dream_ban import handle_dream_ban, handle_dream_unban, handle_dream_banlist
			if first_arg in ("--ban", "-ban"):
				return await handle_dream_ban(user, [first_arg] + cmd_args[1:], reply=reply, message=message, get_client=get_client)
			elif first_arg in ("--unban", "-unban"):
				return await handle_dream_unban(user, [first_arg] + cmd_args[1:], reply=reply, message=message)
			elif first_arg in ("--banlist", "-banlist"):
				return await handle_dream_banlist(user, [first_arg] + cmd_args[1:], reply=reply, message=message)

	target_ref = reply or message
	return await handle_dream_command(user, args, message=target_ref)



