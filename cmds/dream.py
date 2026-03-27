from lumaai import LumaAI
import requests
import asyncio
import discord
import do_not_push
import time
import argparse
import shlex
import math
import os
import csv
from datetime import datetime

# Dictionary to track user cooldowns
user_cooldowns = {}
pending_logs = {}

def log_dream_command(user_id, username, prompt, generation_type, media_url=None, status="success"):

	log_file = "db/dream_logs.csv"
	
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


def add_banned_user(user_id, username, prompt):
	
	banned_file = "db/dream_banned_users.csv"

	file_exists = os.path.isfile(banned_file)
	
	os.makedirs(os.path.dirname(banned_file), exist_ok=True)
	
	timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	
	with open(banned_file, 'a', newline='', encoding='utf-8') as f:
		writer = csv.writer(f)

		if not file_exists:
			writer.writerow(['timestamp', 'user_id', 'username', 'banned_prompt'])
		
		writer.writerow([timestamp, user_id, username, prompt])


def is_user_banned(user_id):
	
	banned_file = "db/dream_banned_users.csv"
	
	if not os.path.isfile(banned_file):
		return False
	
	with open(banned_file, 'r', newline='', encoding='utf-8') as f:
		reader = csv.DictReader(f)
		for row in reader:
			if str(row['user_id']) == str(user_id):
				return True
	
	return False

async def handle_dream_command(user, args, message=None):
	try:
		if is_user_banned(user.id):
			return "You are not allowed to use the dream command."
		
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
		
		user_id = user.id
		is_admin = user_id in do_not_push.LUMA_USERS
		
		
		# Determine current generation type - combine video and image-to-video into "video"
		current_generation_type = "video" if (is_video or is_image_to_video) else "image"
		current_time = time.time()

		if not is_admin:
			cooldown_period = 60
			
			if user_id in user_cooldowns and current_generation_type in user_cooldowns[user_id]:
				last_used = user_cooldowns[user_id][current_generation_type]
				time_elapsed = current_time - last_used
				time_remaining = cooldown_period - time_elapsed
				
				if time_remaining > 0:
					minutes = int(time_remaining // 60)
					seconds = int(time_remaining % 60)
					if minutes > 0:
						time_str = f"{minutes} minute{'s' if minutes > 1 else ''} and {seconds} second{'s' if seconds != 1 else ''}"
					else:
						time_str = f"{seconds} second{'s' if seconds != 1 else ''}"
					return f"You're on cooldown for {current_generation_type} generation for {time_str}. Please try again later."
		
		requires_replied_image = is_image_to_video or has_iref or has_sref or has_cref or has_modify
		
		image_url = None
		if requires_replied_image:
			if not message:
				return "This generation type requires you to reply to a message containing an image."
				
			# In your implementation, 'message' is already the MessageReference object
			# Get the resolved message directly
			replied_to = message.resolved
			if not replied_to:
				return "Could not find the message you're replying to."
			
			# Check if the message has attachments and at least one is an image
			image_url = None
			if replied_to.attachments:
				for attachment in replied_to.attachments:
					if hasattr(attachment, "content_type") and attachment.content_type and attachment.content_type.startswith('image/'):
						image_url = attachment.url
						break
			
			# Check for embeds with images if no attachments found
			if not image_url and replied_to.embeds:
				for embed in replied_to.embeds:
					if embed.image:
						image_url = embed.image.url
						break
			
			if not image_url:
				return "The message you replied to doesn't contain any images."
			
			image_response = requests.get(image_url)
			if image_response.status_code != 200:
				return f"Failed to download the image from Discord CDN: HTTP {image_response.status_code}"
		
		num_advanced_flags = sum([has_iref, has_sref, has_cref, has_modify])
		if num_advanced_flags > 1:
			return "Please use only one advanced image reference flag at a time (-iref, -sref, -cref, or -modify)."
		
		# Allow prompt to be empty ONLY if we are doing modify or image_to_video
		if not prompt and not is_image_to_video and not has_modify:
			usage_msg = "Please provide a prompt for generation. Usage: ;;dream <prompt>"
			if is_admin:
				usage_msg += "\nAdvanced: `-v` (video), `-i2v` (image to video), `-iref`, `-sref`, `-cref`, `-modify`"
			return usage_msg
		
		# Check content moderation
		if prompt:
			openai_key = getattr(do_not_push, "OPENAI_API_KEY", "")
			if openai_key:
				try:
					mod_response = requests.post(
						"https://api.openai.com/v1/moderations",
						headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
						json={"input": prompt},
						timeout=5
					)
					if mod_response.status_code == 200:
						mod_data = mod_response.json()
						if mod_data["results"][0]["flagged"]:
							add_banned_user(
								user_id=user.id,
								username=user.name if hasattr(user, 'name') else str(user),
								prompt=prompt
							)
							return "Your prompt was flagged by our safety system for inappropriate content. You have been banned from using the dream command."
				except Exception as e:
					print(f"Moderation API error: {e}")

		# Initialize Luma AI client with auth_token
		client = LumaAI(auth_token=do_not_push.LUMA_API_KEY)
		
		# Get specific generation type for display purposes
		display_generation_type = "image-to-video" if is_image_to_video else ("video" if is_video else "image")

		log_dream_command(
			user_id=user.id,
			username=user.name if hasattr(user, 'name') else str(user),
			prompt=prompt,
			generation_type=display_generation_type,
			media_url=None  # URL not available yet
		)
		
		initial_response = f"Creating {display_generation_type} for prompt: '{prompt}'... This might take a few minutes."
		
		# Create the generation request based on type
		if is_image_to_video:
			# Create image-to-video generation
			generation = client.generations.create(
				prompt=prompt if prompt else "Transform this image into a cinematic video",
				model="ray-2",
				keyframes={
					"frame0": {
						"type": "image",
						"url": image_url
					}
				},
				resolution="540p",
				duration="5s"
			)

		elif is_video:
			# Use specific parameters for video generation
			generation = client.generations.video.create(
				prompt=prompt,
				model="ray-2",
				resolution="540p",
				duration="5s"
			)
		else:
			# Base image generation parameters
			kwargs = {
				"prompt": prompt,
				"model": "photon-1"
			}
			
			if image_url:
				# Clamp weight parameter naturally
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
					kwargs["character_ref"] = {"identity0": {"images": [image_url]}} # Character ref does not accept weight
				elif has_modify:
					kwargs["modify_image_ref"] = ref_dict
			
			generation = client.generations.image.create(**kwargs)
		
		# Poll until completion
		completed = False
		polling_count = 0
		max_polling = 120  # Maximum poll attempts (10 minutes with 5 second intervals)
		
		while not completed and polling_count < max_polling:
			generation = client.generations.get(id=generation.id)
			
			if generation.state == "completed":
				completed = True
			elif generation.state == "failed":
				failure_reason = getattr(generation, 'failure_reason', 'Unknown reason')
				if "moderation" in failure_reason.lower() or "400" in failure_reason:
					add_banned_user(
						user_id=user.id,
						username=user.name if hasattr(user, 'name') else str(user),
						prompt=prompt
					)
					return "Your generation request violated content moderation policies. You have been banned from using the dream command."
				
				log_dream_command(
					user_id=user.id,
					username=user.name if hasattr(user, 'name') else str(user),
					prompt=prompt,
					generation_type=display_generation_type,
					media_url=None,
					status="fail: " + failure_reason
				)
				return f"{display_generation_type.capitalize()} generation failed: {failure_reason}"
			
			# Wait before checking again (longer interval for videos)
			polling_interval = 5 if (is_video or is_image_to_video) else 3
			await asyncio.sleep(polling_interval)
			polling_count += 1
			
		if not completed:
			log_dream_command(
				user_id=user.id,
				username=user.name if hasattr(user, 'name') else str(user),
				prompt=prompt,
				generation_type=display_generation_type,
				media_url=None,
				status="fail: timeout"
			)
			return f"{display_generation_type.capitalize()} generation timed out. Please try again later."
		
		# Get the media URL and appropriate file extension
		if is_video or is_image_to_video:
			media_url = generation.assets.video
			file_extension = "mp4"
			discord_filename = "dream_video_result.mp4"
		else:
			media_url = generation.assets.image
			file_extension = "jpg"
			discord_filename = "dream_result.jpg"

		log_dream_command(
			user_id=user.id,
			username=user.name if hasattr(user, 'name') else str(user),
			prompt=prompt,
			generation_type=display_generation_type,
			media_url=media_url,
			status="success"
		)
		
		# Download the generated content
		response = requests.get(media_url, stream=True)
		file_path = f'{generation.id}.{file_extension}'
		
		with open(file_path, 'wb') as file:
			file.write(response.content)
		
		# Create a Discord file object
		discord_file = discord.File(
			file_path,
			filename=discord_filename,
			description=f"Dream {display_generation_type} completed for '{prompt}'"
		)
		
		# Record the successful generation for cooldown
		if not is_admin:
			if user_id not in user_cooldowns:
				user_cooldowns[user_id] = {}
			user_cooldowns[user_id][current_generation_type] = time.time()
			
		return discord_file
		
	except Exception as e:
		error_message = str(e)
		log_dream_command(
			user_id=user.id,
			username=user.name if hasattr(user, 'name') else str(user),
			prompt=prompt if 'prompt' in locals() else "unknown",
			generation_type=display_generation_type if 'display_generation_type' in locals() else "unknown",
			media_url=None,
			status=f"error: {error_message}"
		)
		return f"Error generating content: {error_message}"