import io
import asyncio
from typing import Optional, Union, Callable
import aiohttp

try:
	import luma_agents
	from luma_agents import AsyncLuma
except ImportError:
	luma_agents = None
	AsyncLuma = None

import discord
import constants
import do_not_push
import argparse
import os
import csv
from datetime import datetime
from ui import (
	error_embed,
	warning_embed,
	get_http_session,
	extract_media_urls,
	guess_video_mime_type,
	validate_video_url,
	MAX_IMAGE_DOWNLOAD_SIZE,
)

# Max download size for Luma AI generated media (100 MB for videos)
MAX_DREAM_DOWNLOAD_SIZE = 100 * 1024 * 1024  # 100 MB

# --- Luma Agents defaults & valid values (from the luma-agents SDK types) ---

DEFAULT_IMAGE_MODEL = "uni-1"
MAX_IMAGE_MODEL = "uni-1-max"
VIDEO_MODEL = "ray-3.2"
DEFAULT_VIDEO_RESOLUTION = "540p"
DEFAULT_VIDEO_DURATION = "5s"

VALID_ASPECT_RATIOS = ("1:1", "3:2", "2:3", "4:3", "3:4", "16:9", "9:16", "21:9", "2:1", "1:2", "3:1", "1:3")
VALID_VIDEO_RESOLUTIONS = ("360p", "540p", "720p", "1080p")
VALID_VIDEO_DURATIONS = ("5s", "10s")
VALID_EDIT_STRENGTHS = ("adhere_1", "adhere_2", "adhere_3", "flex_1", "flex_2", "flex_3", "reimagine_1", "reimagine_2", "reimagine_3")
VALID_LAYER_RESOLUTIONS = ("1k", "2k")

# High-cost options restricted to admins
ADMIN_ONLY_FLAGS = {"max", "web_search", "video_edit", "video_reframe", "layering"}
ADMIN_VIDEO_RESOLUTIONS = {"1080p"}
ADMIN_VIDEO_DURATIONS = {"10s"}

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


def _api_error_detail(error) -> str:
	"""Extract a human-readable detail message from a luma_agents APIStatusError."""
	try:
		body = getattr(error, 'body', None)
		if isinstance(body, dict):
			detail = body.get('detail')
			if isinstance(detail, str):
				return detail
			if isinstance(detail, dict):
				return str(detail)
			err = body.get('error')
			if isinstance(err, dict) and err.get('message'):
				return str(err['message'])
	except Exception:
		pass
	return str(error)


def _is_content_moderated_error(error) -> bool:
	"""Detect Luma's synchronous content-policy rejection in an APIStatusError body."""
	try:
		body = getattr(error, 'body', None)
		if isinstance(body, dict):
			# Shape 1: {'detail': {'error': {'code': 'content_moderated', ...}}}
			# Shape 2: {'error': {'code': 'content_moderated', ...}}
			for container in (body.get('detail'), body):
				if isinstance(container, dict):
					err = container.get('error')
					if isinstance(err, dict) and err.get('code') == 'content_moderated':
						return True
			# Shape 3: {'detail': '...content policy...'} string fallbacks
			detail = body.get('detail')
			if isinstance(detail, str) and 'content' in detail.lower() and ('moderat' in detail.lower() or 'policy' in detail.lower()):
				return True
	except Exception:
		pass
	return False


def _build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(add_help=False)
	# Generation modes (mutually exclusive, validated later)
	parser.add_argument('-v', '--video', action='store_true', help='Generate a video instead of an image')
	parser.add_argument('-i2v', '--image-to-video', action='store_true', help='Transform a replied image into a video')
	parser.add_argument('-modify', '--modify-image', action='store_true', help='Edit the replied image with a prompt')
	parser.add_argument('-iref', '--image-ref', action='store_true', help='Use replied image as a content/style reference')
	parser.add_argument('-vedit', '--video-edit', action='store_true', help='Edit a replied video with a prompt')
	parser.add_argument('-reframe', '--video-reframe', action='store_true', help='Re-crop a replied video to a new aspect ratio')
	parser.add_argument('-layers', '--layering', action='store_true', help='Decompose a replied image into layers')
	# Options
	parser.add_argument('-max', '--max-quality', action='store_true', help='Use uni-1-max image model')
	parser.add_argument('-ar', '--aspect-ratio', type=str, default=None, help='Aspect ratio (e.g. 16:9)')
	parser.add_argument('-res', '--resolution', type=str, default=None, help='Video resolution (360p/540p/720p/1080p)')
	parser.add_argument('-d', '--duration', type=str, default=None, help='Video duration (5s/10s)')
	parser.add_argument('-loop', action='store_true', help='Seamless looping video')
	parser.add_argument('-end', '--end-frame', action='store_true', help='Use 2nd replied image as video end frame')
	parser.add_argument('-manga', action='store_true', help='Manga style preset')
	parser.add_argument('-png', action='store_true', help='PNG output format')
	parser.add_argument('-web', '--web-search', action='store_true', help='Web-search grounding')
	parser.add_argument('-strength', type=str, default=None, help='Video edit strength (adhere_1-3/flex_1-3/reimagine_1-3)')
	parser.add_argument('-lres', '--layer-resolution', type=str, default=None, help='Layering resolution (1k/2k)')
	parser.add_argument('prompt', nargs='*', help='The prompt for generation')
	return parser

def _usage_embed(is_admin: bool) -> discord.Embed:
	embed = discord.Embed(
		title="Dream Command Usage",
		description="Generate AI images and videos using Luma AI.",
		color=discord.Color.blurple()
	)
	embed.add_field(
		name="Basic Usage",
		value=(
			"• `;;dream <prompt>` : Generate an image\n"
			"• `;;dream -v <prompt>` : Generate a 5s video\n"
			"• `;;dream -i2v [prompt]` : Animate a replied image\n"
			"• `;;dream -modify <prompt>` : Edit a replied image"
		),
		inline=False
	)
	embed.add_field(
		name="Options",
		value=(
			"• **`-ar <ratio>`** : Aspect ratio (" + ", ".join(VALID_ASPECT_RATIOS[:7]) + ", …)\n"
			"• **`-res <360p|540p|720p>`** : Video resolution (default 540p)\n"
			"• **`-d <5s>`** : Video duration\n"
			"• **`-loop`** : Seamless loop (video)\n"
			"• **`-end`** : 2nd replied image as video end frame\n"
			"• **`-iref`** : Replied image as reference\n"
			"• **`-manga`** : Manga style preset\n"
			"• **`-png`** : PNG output"
		),
		inline=False
	)
	if is_admin:
		embed.add_field(
			name="Admin Options",
			value=(
				"• **`-max`** : uni-1-max image quality\n"
				"• **`-res 1080p` / `-d 10s`** : Top-tier video\n"
				"• **`-web`** : Web-search grounding\n"
				"• **`-vedit [-strength <preset>]`** : Edit replied video\n"
				"• **`-reframe -ar <ratio>`** : Re-crop replied video\n"
				"• **`-layers [-lres <1k|2k>]`** : Split replied image into layers"
			),
			inline=False
		)
	return embed


async def handle_dream_command(user, args, message=None):
	prompt = "unknown"
	display_generation_type = "unknown"
	try:
		user_id = user.id
		is_admin = user_id in getattr(do_not_push, 'LUMA_USERS', []) or user_id in getattr(do_not_push, 'ADMINS', [])

		if not is_admin and await asyncio.to_thread(is_user_banned, user_id):
			return error_embed("You are not allowed to use the dream command.", title="🚫 Access Denied")

		if AsyncLuma is None:
			return error_embed("The `luma-agents` package is not installed. Please ask the bot owner to update dependencies.", title="❌ Configuration Error")

		# Parse the command arguments. Plain whitespace split (not shlex) so
		# apostrophes/quotes in free-text prompts (e.g. "a cat's life") never break parsing.
		parser = _build_parser()
		args_string = " ".join(args[1:]) if args and args[0].lower() == "dream" else " ".join(args)
		try:
			parsed = parser.parse_args(args_string.split())
			prompt = " ".join(parsed.prompt).strip()
		except (Exception, SystemExit):
			# argparse raises SystemExit on bad flags / missing values
			return error_embed("Could not parse arguments. Check your flags.", title="❌ Invalid Arguments")

		# --- Mode selection (mutually exclusive) ---
		modes = {
			"video": parsed.video,
			"image-to-video": parsed.image_to_video,
			"image_edit": parsed.modify_image,
			"video_edit": parsed.video_edit,
			"video_reframe": parsed.video_reframe,
			"layering": parsed.layering,
		}
		active_modes = [m for m, on in modes.items() if on]
		if len(active_modes) > 1:
			return warning_embed(
				"Please use only one mode flag at a time (`-v`, `-i2v`, `-modify`, `-vedit`, `-reframe`, `-layers`).",
				title="⚠️ Conflicting Flags"
			)
		mode = active_modes[0] if active_modes else "image"
		if parsed.image_ref and mode != "image":
			return warning_embed("`-iref` only applies to plain image generation.", title="⚠️ Incompatible Options")
		is_video_type = mode in ("video", "image-to-video", "video_edit", "video_reframe")

		# --- Admin gating ---
		if not is_admin:
			used_admin_flags = []
			if parsed.max_quality:
				used_admin_flags.append("`-max`")
			if parsed.web_search:
				used_admin_flags.append("`-web`")
			if parsed.video_edit:
				used_admin_flags.append("`-vedit`")
			if parsed.video_reframe:
				used_admin_flags.append("`-reframe`")
			if parsed.layering:
				used_admin_flags.append("`-layers`")
			if parsed.resolution and parsed.resolution in ADMIN_VIDEO_RESOLUTIONS:
				used_admin_flags.append(f"`-res {parsed.resolution}`")
			if parsed.duration and parsed.duration in ADMIN_VIDEO_DURATIONS:
				used_admin_flags.append(f"`-d {parsed.duration}`")
			if used_admin_flags:
				return warning_embed(
					f"The following option(s) are admin-only: {', '.join(used_admin_flags)}.",
					title="⚠️ Admin-Only Option"
				)

		# --- Option validation ---
		def _clean_opt(value: str) -> str:
			return value.strip().strip('"').strip("'").strip().lower()

		aspect_ratio = None
		if parsed.aspect_ratio:
			aspect_ratio = _clean_opt(parsed.aspect_ratio)
			if aspect_ratio not in VALID_ASPECT_RATIOS:
				return warning_embed(f"Invalid aspect ratio `{parsed.aspect_ratio}`. Valid: {', '.join(VALID_ASPECT_RATIOS)}", title="⚠️ Invalid Aspect Ratio")

		resolution = None
		if parsed.resolution:
			resolution = _clean_opt(parsed.resolution)
			if resolution not in VALID_VIDEO_RESOLUTIONS:
				return warning_embed(f"Invalid resolution `{parsed.resolution}`. Valid: {', '.join(VALID_VIDEO_RESOLUTIONS)}", title="⚠️ Invalid Resolution")

		duration = None
		if parsed.duration:
			duration = _clean_opt(parsed.duration)
			if duration not in VALID_VIDEO_DURATIONS:
				return warning_embed(f"Invalid duration `{parsed.duration}`. Valid: {', '.join(VALID_VIDEO_DURATIONS)}", title="⚠️ Invalid Duration")

		strength = None
		if parsed.strength:
			strength = _clean_opt(parsed.strength)
			if strength not in VALID_EDIT_STRENGTHS:
				return warning_embed(f"Invalid strength `{parsed.strength}`. Valid: {', '.join(VALID_EDIT_STRENGTHS)}", title="⚠️ Invalid Strength")

		layer_resolution = None
		if parsed.layer_resolution:
			layer_resolution = _clean_opt(parsed.layer_resolution)
			if layer_resolution not in VALID_LAYER_RESOLUTIONS:
				return warning_embed(f"Invalid layer resolution `{parsed.layer_resolution}`. Valid: {', '.join(VALID_LAYER_RESOLUTIONS)}", title="⚠️ Invalid Layer Resolution")

		if parsed.loop and duration == "10s":
			return warning_embed("`-loop` is not supported with `-d 10s`.", title="⚠️ Incompatible Options")
		if parsed.loop and not is_video_type:
			return warning_embed("`-loop` only applies to video generation.", title="⚠️ Incompatible Options")
		if parsed.end_frame and not (is_video_type and mode != "video_edit" and mode != "video_reframe"):
			return warning_embed("`-end` only applies to video / image-to-video generation.", title="⚠️ Incompatible Options")
		if strength and mode != "video_edit":
			return warning_embed("`-strength` only applies to `-vedit`.", title="⚠️ Incompatible Options")
		if layer_resolution and mode != "layering":
			return warning_embed("`-lres` only applies to `-layers`.", title="⚠️ Incompatible Options")
		if (resolution or duration) and not is_video_type:
			return warning_embed("`-res` / `-d` only apply to video generation.", title="⚠️ Incompatible Options")
		if (parsed.manga or parsed.png) and is_video_type:
			return warning_embed("`-manga` / `-png` only apply to image generation.", title="⚠️ Incompatible Options")
		if mode == "video_reframe" and not aspect_ratio:
			return warning_embed("`-reframe` requires a target aspect ratio, e.g. `;;dream -reframe -ar 9:16`.", title="⚠️ Aspect Ratio Required")

		# --- Media requirements ---
		needs_image = mode in ("image-to-video", "image_edit", "layering") or (mode == "image" and parsed.image_ref)
		needs_video = mode in ("video_edit", "video_reframe")

		image_urls: list[str] = []
		video_urls: list[str] = []
		if message and (needs_image or needs_video or parsed.end_frame or mode == "image-to-video"):
			image_urls, video_urls = extract_media_urls(reply=message)

		if needs_image and not image_urls:
			return warning_embed("This mode requires you to reply to a message containing an image.", title="⚠️ Image Required")
		if needs_video and not video_urls:
			return warning_embed("This mode requires you to reply to a message containing a video.", title="⚠️ Video Required")
		if parsed.end_frame and len(image_urls) < 2:
			return warning_embed("`-end` requires a replied message containing two images (start + end frame).", title="⚠️ Two Images Required")

		# --- Video source validation ---
		# Verify the video URL is reachable, is actually a video, and is within size limits
		# before sending it to the Luma API (prevents abuse and wasted API credits).
		if needs_video and video_urls:
			is_valid, detected_mime, err_msg = await validate_video_url(video_urls[0])
			if not is_valid:
				return error_embed(err_msg, title="❌ Invalid Video")

		# --- Prompt requirements ---
		prompt_optional = mode in ("image-to-video", "image_edit", "video_reframe", "layering")
		if not prompt and not prompt_optional:
			return _usage_embed(is_admin)
		if mode == "layering" and len(prompt) > 500:
			return warning_embed("The `-layers` prompt is limited to 500 characters.", title="⚠️ Prompt Too Long")

		# --- Content moderation ---
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

		client = AsyncLuma(auth_token=do_not_push.LUMA_API_KEY)

		# --- Build the unified generation request ---
		display_generation_type = mode
		create_kwargs: dict = {
			"prompt": prompt,
			"user_id": str(user_id),
		}

		if mode == "image":
			create_kwargs["type"] = "image"
			create_kwargs["model"] = MAX_IMAGE_MODEL if parsed.max_quality else DEFAULT_IMAGE_MODEL
			if aspect_ratio:
				create_kwargs["aspect_ratio"] = aspect_ratio
			if parsed.manga:
				create_kwargs["style"] = "manga"
			if parsed.png:
				create_kwargs["output_format"] = "png"
			if parsed.web_search:
				create_kwargs["web_search"] = True
			if parsed.image_ref and image_urls:
				create_kwargs["image_ref"] = [{"url": u} for u in image_urls[:9]]

		elif mode == "image_edit":
			create_kwargs["type"] = "image_edit"
			create_kwargs["model"] = MAX_IMAGE_MODEL if parsed.max_quality else DEFAULT_IMAGE_MODEL
			create_kwargs["source"] = {"url": image_urls[0]}
			if not prompt:
				create_kwargs["prompt"] = "Enhance this image"
			if aspect_ratio:
				create_kwargs["aspect_ratio"] = aspect_ratio
			if parsed.png:
				create_kwargs["output_format"] = "png"
			if len(image_urls) > 1:
				create_kwargs["image_ref"] = [{"url": u} for u in image_urls[1:9]]

		elif mode == "layering":
			create_kwargs["type"] = "layering"
			create_kwargs["model"] = DEFAULT_IMAGE_MODEL
			create_kwargs["source"] = {"url": image_urls[0]}
			if not prompt:
				create_kwargs["prompt"] = "Split this image into layers"
			create_kwargs["layering"] = {"resolution": layer_resolution or "1k"}

		elif mode == "video_edit":
			create_kwargs["type"] = "video_edit"
			create_kwargs["model"] = VIDEO_MODEL
			create_kwargs["source"] = {"url": video_urls[0], "media_type": guess_video_mime_type(video_urls[0])}
			video_opts: dict = {}
			if resolution:
				video_opts["resolution"] = resolution
			edit_opts: dict = {}
			if strength:
				edit_opts["strength"] = strength
			if edit_opts:
				video_opts["edit"] = edit_opts
			if video_opts:
				create_kwargs["video"] = video_opts

		elif mode == "video_reframe":
			create_kwargs["type"] = "video_reframe"
			create_kwargs["model"] = VIDEO_MODEL
			create_kwargs["source"] = {"url": video_urls[0], "media_type": guess_video_mime_type(video_urls[0])}
			create_kwargs["aspect_ratio"] = aspect_ratio
			if not prompt:
				create_kwargs["prompt"] = "Reframe this video"
			video_opts = {}
			if resolution:
				video_opts["resolution"] = resolution
			if video_opts:
				create_kwargs["video"] = video_opts

		else:  # video / image-to-video
			create_kwargs["type"] = "video"
			create_kwargs["model"] = VIDEO_MODEL
			if not prompt:
				create_kwargs["prompt"] = "Transform this image into a cinematic video"
			if aspect_ratio:
				create_kwargs["aspect_ratio"] = aspect_ratio
			video_opts = {
				"resolution": resolution or DEFAULT_VIDEO_RESOLUTION,
				"duration": duration or DEFAULT_VIDEO_DURATION,
			}
			if parsed.loop:
				video_opts["loop"] = True
			if image_urls:
				video_opts["start_frame"] = {"url": image_urls[0]}
				if parsed.end_frame and len(image_urls) >= 2:
					video_opts["end_frame"] = {"url": image_urls[1]}
			create_kwargs["video"] = video_opts

		await asyncio.to_thread(
			log_dream_command,
			user_id=user.id,
			username=user.name if hasattr(user, 'name') else str(user),
			prompt=prompt,
			generation_type=display_generation_type,
			media_url=None
		)

		try:
			generation = await client.generations.create(**create_kwargs)
		except luma_agents.UnprocessableEntityError as e:
			# Luma rejects policy-violating prompts synchronously with HTTP 422 and
			# body {'error': {'code': 'content_moderated', ...}}. Ban on that.
			if _is_content_moderated_error(e):
				if not is_admin:
					await asyncio.to_thread(
						add_banned_user,
						user_id=user.id,
						username=user.name if hasattr(user, 'name') else str(user),
						prompt=prompt
					)
					await asyncio.to_thread(
						log_dream_command,
						user_id=user.id,
						username=user.name if hasattr(user, 'name') else str(user),
						prompt=prompt,
						generation_type=display_generation_type,
						media_url=None,
						status="fail: content_moderated (sync 422, banned)"
					)
					return error_embed("Your generation request violated content moderation policies. You have been banned from using the dream command.", title="🚫 Moderation Violation")
				return warning_embed("Your prompt was rejected by Luma's content moderation policy.", title="⚠️ Moderation Violation")
			return error_embed(f"Luma rejected the request: {_api_error_detail(e)}", title="❌ Invalid Request")
		except luma_agents.BadRequestError as e:
			if _is_content_moderated_error(e):
				if not is_admin:
					await asyncio.to_thread(
						add_banned_user,
						user_id=user.id,
						username=user.name if hasattr(user, 'name') else str(user),
						prompt=prompt
					)
					await asyncio.to_thread(
						log_dream_command,
						user_id=user.id,
						username=user.name if hasattr(user, 'name') else str(user),
						prompt=prompt,
						generation_type=display_generation_type,
						media_url=None,
						status="fail: content_moderated (sync 400, banned)"
					)
					return error_embed("Your generation request violated content moderation policies. You have been banned from using the dream command.", title="🚫 Moderation Violation")
				return warning_embed("Your prompt was rejected by Luma's content moderation policy.", title="⚠️ Moderation Violation")
			return error_embed(f"Luma rejected the request: {_api_error_detail(e)}", title="❌ Invalid Request")
		except luma_agents.RateLimitError:
			return error_embed("Luma is rate limiting us right now. Please try again in a minute.", title="⏳ Rate Limited")
		except luma_agents.AuthenticationError:
			return error_embed("Luma API authentication failed. Please ask the bot owner to check the API key.", title="❌ Authentication Error")
		except luma_agents.APIConnectionError:
			return error_embed("Could not reach the Luma API. Please try again later.", title="❌ Connection Error")

		# Poll until completion
		completed = False
		polling_count = 0
		max_polling = 120

		while not completed and polling_count < max_polling:
			try:
				generation = await client.generations.get(generation.id)
			except luma_agents.APIError as e:
				print(f"Dream polling error: {e}")
				await asyncio.sleep(3)
				polling_count += 1
				continue

			if generation.state == "completed":
				completed = True
			elif generation.state == "failed":
				failure_code = getattr(generation, 'failure_code', None) or ""
				failure_reason = getattr(generation, 'failure_reason', None) or "Unknown reason"

				if failure_code == "content_moderated":
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
					status=f"fail: {failure_code} {failure_reason}".strip()
				)
				return error_embed(f"{display_generation_type.capitalize()} generation failed: {failure_reason}", title="❌ Generation Failed")

			polling_interval = 5 if is_video_type else 3
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

		# --- Collect outputs ---
		outputs = list(generation.output or [])
		if not outputs:
			return error_embed("Generation completed but returned no output.", title="❌ Generation Error")

		if is_video_type:
			media_url = next((o.url for o in outputs if o.type == "video"), outputs[0].url)
		else:
			media_url = next((o.url for o in outputs if o.type == "image"), outputs[0].url)

		await asyncio.to_thread(
			log_dream_command,
			user_id=user.id,
			username=user.name if hasattr(user, 'name') else str(user),
			prompt=prompt,
			generation_type=display_generation_type,
			media_url=media_url,
			status="success"
		)

		session = await get_http_session()

		if mode == "layering":
			# Download every layer and send them all in one message
			files = []
			for i, out in enumerate(outputs):
				async with session.get(out.url) as resp:
					if resp.status != 200:
						continue
					content = await resp.read()
					if len(content) > MAX_IMAGE_DOWNLOAD_SIZE:
						continue
				label = "layer"
				if getattr(out, "layer", None) and getattr(out.layer, "label", None):
					label = "".join(c if c.isalnum() or c in "-_" else "_" for c in out.layer.label.lower())
				buf = io.BytesIO(content)
				buf.seek(0)
				files.append(discord.File(fp=buf, filename=f"dream_layer_{i}_{label}.png", description=f"Layer {i}: {label}"))
			if not files:
				return error_embed("Failed to download the generated layers.", title="❌ Download Failed")
			return {"files": files}

		async with session.get(media_url) as media_response:
			if media_response.status != 200:
				return error_embed(f"Failed to download generated media: HTTP {media_response.status}")
			media_content = await media_response.read()
			if len(media_content) > MAX_DREAM_DOWNLOAD_SIZE:
				size_mb = len(media_content) / (1024 * 1024)
				limit_mb = MAX_DREAM_DOWNLOAD_SIZE / (1024 * 1024)
				return error_embed(f"Generated media too large ({size_mb:.1f} MB). Maximum: {limit_mb:.0f} MB.", title="❌ Download Too Large")

		buffer = io.BytesIO(media_content)
		buffer.seek(0)

		if is_video_type:
			discord_filename = "dream_video_result.mp4"
		else:
			discord_filename = "dream_result.png" if parsed.png else "dream_result.jpg"

		return discord.File(
			fp=buffer,
			filename=discord_filename,
			description=f"Dream {display_generation_type} completed for '{prompt}'"
		)

	except Exception as e:
		error_message = str(e)
		try:
			await asyncio.to_thread(
				log_dream_command,
				user_id=user.id,
				username=user.name if hasattr(user, 'name') else str(user),
				prompt=prompt,
				generation_type=display_generation_type,
				media_url=None,
				status=f"error: {error_message}"
			)
		except Exception:
			pass
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
