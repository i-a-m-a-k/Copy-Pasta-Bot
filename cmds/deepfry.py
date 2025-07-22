import io
import aiohttp
from discord import File, Attachment
from PIL import Image
import cv2
import numpy as np
import deeppyer
import os
from typing import Optional, Union
import constants

# Get the absolute path to the cascade files
CASCADE_PATH = os.path.dirname(cv2.__file__) + "/data/haarcascade_frontalface_default.xml"
EYE_CASCADE_PATH = os.path.dirname(cv2.__file__) + "/data/haarcascade_eye.xml"

def is_supported_format(attachment: Attachment) -> bool:

    # List of explicitly supported MIME types
    supported_types = [
        'image/png',
        'image/jpeg',
        'image/gif',
        'image/webp',
        'image/tiff'
    ]

    return (attachment.content_type in supported_types or
            (attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.tiff'))))

async def process_image(image_data: bytes) -> Optional[Image.Image]:
    """
    Process image data into a PIL Image, handling different formats.

    Args:
        image_data: Raw image bytes
    Returns:
        Optional[Image.Image]: Processed PIL Image or None if processing fails
    """
    try:
        img = Image.open(io.BytesIO(image_data))

        # Convert GIF to static image (first frame)
        if img.format == 'GIF' and img.is_animated:
            img.seek(0)

        # Convert to RGB while preserving quality
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            # Create white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            # Paste using alpha channel as mask
            background.paste(img, mask=img.split()[-1])
            img = background
        else:
            img = img.convert('RGB')

        return img
    except Exception as e:
        print(f"Error processing image: {str(e)}")
        return None

def add_glowing_eyes(cv_img, faces):
    """
    Add glowing eyes effect to detected faces.

    Args:
        cv_img: The image in OpenCV format.
        faces: Detected face coordinates.
    Returns:
        cv_img: Image with glowing eyes.
    """
    try:
        eye_cascade = cv2.CascadeClassifier(EYE_CASCADE_PATH)
        if eye_cascade.empty():
            raise Exception("Failed to load eye cascade classifier")

        for (x, y, w, h) in faces:
            roi_color = cv_img[y:y+h, x:x+w]
            gray = cv2.cvtColor(roi_color, cv2.COLOR_BGR2GRAY)
            eyes = eye_cascade.detectMultiScale(gray, 1.1, 10)

            for (ex, ey, ew, eh) in eyes:
                eye_center = (x + ex + ew // 2, y + ey + eh // 2)
                radius = int(min(ew, eh) / 2)
                cv2.circle(cv_img, eye_center, radius, (255, 255, 255), -1)  # White base
                cv2.circle(cv_img, eye_center, radius, (0, 255, 255), 15)    # Outer glow
                cv2.circle(cv_img, eye_center, radius, (255, 0, 0), 7)       # Inner glow

        return cv_img
    except Exception as e:
        print(f"Error in add_glowing_eyes: {str(e)}")
        return cv_img

async def deep_fry_image(img: Image.Image) -> Image.Image:
    """
    Deep fry an image with face detection and glowing eyes.

    Args:
        img: PIL Image to deep fry
    Returns:
        PIL Image: Deep fried image with glowing eyes
    """
    try:
        # Convert PIL to OpenCV format
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        # Create a copy for face detection to avoid drawing rectangles
        face_detect_img = cv_img.copy()

        # Load face cascade
        face_cascade = cv2.CascadeClassifier(CASCADE_PATH)
        if face_cascade.empty():
            raise Exception("Failed to load face cascade classifier")

        # Detect faces on the copy
        gray = cv2.cvtColor(face_detect_img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)

        # Add glowing eyes to original image
        cv_img = add_glowing_eyes(cv_img, faces)

        # Add red tint to faces on original image
        for (x, y, w, h) in faces:
            roi = cv_img[y:y+h, x:x+w]
            red_tint = roi.copy()
            red_tint[:, :, 2] = np.clip(red_tint[:, :, 2] * 1.5, 0, 255)
            cv_img[y:y+h, x:x+w] = cv2.addWeighted(roi, 0.5, red_tint, 0.5, 0)

        # Convert back to PIL
        img = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))

        # Use deeppyer for additional deep frying effects
        fried_img = await deeppyer.deepfry(img, flares=False)
        return fried_img

    except Exception as e:
        print(f"Error in deep_fry_image: {str(e)}")
        return img

async def handle_deepfry_command(reply) -> Union[File, str]:
    """
    Deep fry an image from a message, including captioned images.

    Args:
        reply: The message reference containing the original message with image
    Returns:
        Union[File, str]: The deep-fried image as a Discord file or error message
    """
    if not reply.resolved:
        return constants.REPLY_TO_MESSAGE

    # Check referenced message for attachments or embeds
    attachments = reply.resolved.attachments
    embeds = getattr(reply.resolved, 'embeds', [])

    # Try to get image from attachments first
    image_attachment = None
    for attachment in attachments:
        if is_supported_format(attachment):
            image_attachment = attachment
            break

    # If no valid attachment found, try embeds (for captioned images)
    if not image_attachment and embeds:
        for embed in embeds:
            if embed.image:
                # Create a mock attachment with the embed's image URL
                class MockAttachment:
                    def __init__(self, url):
                        self.url = url
                        self.filename = url.split('/')[-1]
                image_attachment = MockAttachment(embed.image.url)
                break

    if not image_attachment:
        return "Cannot deep fry - no valid image found in the message."

    try:
        # Download the image
        async with aiohttp.ClientSession() as session:
            async with session.get(image_attachment.url) as response:
                if response.status != 200:
                    return "Failed to download the image."
                image_data = await response.read()

        # Process the image
        pil_image = await process_image(image_data)
        if pil_image is None:
            return "Failed to process the image format."

        # Deep fry the image
        fried_img = await deep_fry_image(pil_image)

        # Save to Discord file
        output = io.BytesIO()
        fried_img.save(output, format='PNG')
        output.seek(0)
        return File(output, filename='deepfried.png')

    except Exception as e:
        return f"Error deep frying image: {str(e)}"
