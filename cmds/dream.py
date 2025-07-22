# from lumaai import LumaAI
import requests
import asyncio
import discord
import do_not_push
import time
import argparse
import shlex
from io import BytesIO
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
		parser.add_argument('prompt', nargs='*', help='The prompt for generation')
		
		# Convert args to a string and use shlex to handle quoting
		args_string = " ".join(args[1:]) if args and args[0].lower() == "dream" else " ".join(args)
		try:
			parsed_args = parser.parse_args(shlex.split(args_string))
			is_video = parsed_args.video
			is_image_to_video = parsed_args.image_to_video
			prompt = " ".join(parsed_args.prompt)
		except Exception:
			# Fallback for simpler parsing if argparse fails
			is_video = "-v" in args_string or "--video" in args_string
			is_image_to_video = "-i2v" in args_string or "--image-to-video" in args_string
			
			# Remove the flags from the prompt
			prompt = args_string
			if is_video:
				prompt = prompt.replace("-v", "").replace("--video", "")
			if is_image_to_video:
				prompt = prompt.replace("-i2v", "").replace("--image-to-video", "")
			prompt = prompt.strip()
		
		user_id = user.id
		is_admin = user_id in do_not_push.LUMA_USERS
		
		if not is_admin and (is_video or is_image_to_video):
			return "Sorry, video and image-to-video generation are admin-only features."
		
		# Determine current generation type - combine video and image-to-video into "video"
		current_generation_type = "video" if (is_video or is_image_to_video) else "image"
		current_time = time.time()

		if not is_admin:
			cooldown_period = 300
			
			if user_id in user_cooldowns and current_generation_type in user_cooldowns[user_id]:
				last_used = user_cooldowns[user_id][current_generation_type]
				time_elapsed = current_time - last_used
				time_remaining = cooldown_period - time_elapsed
				
				if time_remaining > 0:
					minutes_remaining = math.ceil(time_remaining / 60)
					return f"You're on cooldown for image generation for {minutes_remaining} more minute{'s' if minutes_remaining > 1 else ''}. Please try again later."
			
			# If we reach here, update the cooldown for the specific type they're using
			if user_id not in user_cooldowns:
				user_cooldowns[user_id] = {}
			
			user_cooldowns[user_id][current_generation_type] = current_time
		
		def upload_image_to_0x0(image_bytes):
			try:
				temp_file = BytesIO(image_bytes)
				files = {'file': ('image.jpg', temp_file, 'application/octet-stream')}
				
				headers = {
					'User-Agent': 'DiscordBotforLuma/1.0 (Discord Image Service)'
				}
				
				response = requests.post("https://0x0.st", files=files, headers=headers)
				
				if response.status_code == 200:
					return response.text.strip()
				return None
			except Exception as e:
				return None
		
		# Image to video requires a reply to a message with an image
		if is_image_to_video:
			if not message:
				return "For image-to-video generation, you must reply to a message containing an image."
				
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
			
			# Upload the image to 0x0.st
			uploaded_image_url = upload_image_to_0x0(image_response.content)
			if not uploaded_image_url:
				return "Failed to upload image to 0x0.st. Please try again later."
		
		if not prompt and not is_image_to_video:
			usage_msg = "Please provide a prompt for generation. Usage: ;;dream <prompt>"
			if is_admin:
				usage_msg += ", ;;dream -v <prompt> for video, or ;;dream -i2v <prompt> to transform an image to video (must reply to a message with an image)"
			return usage_msg
		
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
						"url": uploaded_image_url
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
			generation = client.generations.image.create(prompt=prompt, model="photon-1")
		
		# Poll until completion
		completed = False
		polling_count = 0
		max_polling = 120  # Maximum poll attempts (10 minutes with 5 second intervals)
		
		while not completed and polling_count < max_polling:
			generation = client.generations.get(id=generation.id)
			
			if generation.state == "completed":
				completed = True
			elif generation.state == "failed":
				failure_reason = getattr(generation, 'failure_reason', '')
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