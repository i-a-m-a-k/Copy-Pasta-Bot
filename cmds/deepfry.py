import io
import aiohttp
from discord import File, Attachment
from PIL import Image
import numpy as np
import deeppyer
import os
from typing import Optional, Union

import mediapipe as mp

# Lens flare asset path
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')
LENS_FLARE_PATH = os.path.join(ASSETS_DIR, 'lens_flare.png')

# MediaPipe FaceMesh iris landmarks
# Left iris: 468-472, Right iris: 473-477
# We use the center of each iris (468 for left, 473 for right)
LEFT_IRIS_CENTER = 468
RIGHT_IRIS_CENTER = 473

# Eye corner landmarks for sizing the flare relative to eye width
LEFT_EYE_INNER = 133
LEFT_EYE_OUTER = 33
RIGHT_EYE_INNER = 362
RIGHT_EYE_OUTER = 263

def _load_lens_flare() -> Optional[Image.Image]:
    """Load the lens flare image and convert black background to transparency."""
    try:
        flare = Image.open(LENS_FLARE_PATH).convert('RGBA')
        # Convert black background to transparent using luminance threshold
        data = np.array(flare)
        # Calculate luminance for each pixel
        luminance = (0.299 * data[:,:,0] + 0.587 * data[:,:,1] + 0.114 * data[:,:,2])
        # Set alpha based on luminance (black = transparent, bright = opaque)
        data[:,:,3] = np.clip(luminance * 2, 0, 255).astype(np.uint8)
        # Tint the flare
        data[:,:,0] = np.clip(data[:,:,0].astype(np.float32) * 1.5, 0, 255).astype(np.uint8)  # Boost red
        #data[:,:,1] = (data[:,:,1] * 0.3).astype(np.uint8)  # Suppress green
        data[:,:,2] = (data[:,:,2] * 0.3).astype(np.uint8)  # Suppress blue
        return Image.fromarray(data)
    except Exception as e:
        print(f"Error loading lens flare: {e}")
        return None

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
    """Process image data into a PIL Image, handling different formats."""
    try:
        img = Image.open(io.BytesIO(image_data))
        
        if img.format == 'GIF' and img.is_animated:
            img.seek(0)
        
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1])
            img = background
        else:
            img = img.convert('RGB')
            
        return img
    except Exception as e:
        print(f"Error processing image: {str(e)}")
        return None

def _get_eye_positions(img: Image.Image) -> list[tuple[int, int, int]]:
    """
    Use MediaPipe FaceMesh to detect eye positions.
    
    Returns a list of (center_x, center_y, eye_width) tuples for each detected eye.
    """
    eyes = []
    mp_face_mesh = mp.solutions.face_mesh
    
    img_array = np.array(img)
    h, w = img_array.shape[:2]
    
    with mp_face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=10,
        refine_landmarks=True,  # Required for iris landmarks (468-477)
        min_detection_confidence=0.3
    ) as face_mesh:
        results = face_mesh.process(img_array)
        
        if not results.multi_face_landmarks:
            return eyes
        
        for face_landmarks in results.multi_face_landmarks:
            landmarks = face_landmarks.landmark
            
            # Left eye
            left_cx = int(landmarks[LEFT_IRIS_CENTER].x * w)
            left_cy = int(landmarks[LEFT_IRIS_CENTER].y * h)
            left_inner = int(landmarks[LEFT_EYE_INNER].x * w)
            left_outer = int(landmarks[LEFT_EYE_OUTER].x * w)
            left_eye_width = abs(left_inner - left_outer)
            eyes.append((left_cx, left_cy, left_eye_width))
            
            # Right eye
            right_cx = int(landmarks[RIGHT_IRIS_CENTER].x * w)
            right_cy = int(landmarks[RIGHT_IRIS_CENTER].y * h)
            right_inner = int(landmarks[RIGHT_EYE_INNER].x * w)
            right_outer = int(landmarks[RIGHT_EYE_OUTER].x * w)
            right_eye_width = abs(right_inner - right_outer)
            eyes.append((right_cx, right_cy, right_eye_width))
    
    return eyes

def _overlay_lens_flare(img: Image.Image, eyes: list[tuple[int, int, int]]) -> Image.Image:
    """
    Overlay the lens flare on each detected eye position.
    
    Args:
        img: The base image (RGB).
        eyes: List of (center_x, center_y, eye_width) from _get_eye_positions.
    Returns:
        Image with lens flares composited over eyes.
    """
    flare = _load_lens_flare()
    if flare is None or not eyes:
        return img
    
    # Convert to RGBA for compositing
    img_rgba = img.convert('RGBA')
    
    for (cx, cy, eye_width) in eyes:
        # Scale flare to ~5x the eye width for maximum deep fry effect
        flare_size = max(int(eye_width * 5.0), 30)
        resized_flare = flare.resize((flare_size, flare_size), Image.LANCZOS)
        
        # Calculate paste position (centered on eye)
        paste_x = cx - flare_size // 2
        paste_y = cy - flare_size // 2
        
        # Create a full-size transparent layer and paste the flare onto it
        flare_layer = Image.new('RGBA', img_rgba.size, (0, 0, 0, 0))
        flare_layer.paste(resized_flare, (paste_x, paste_y))
        
        # Use screen blending: result = 1 - (1 - base) * (1 - overlay)
        # This makes the flare additive/bright instead of just pasting over
        base = np.array(img_rgba, dtype=np.float32) / 255.0
        overlay = np.array(flare_layer, dtype=np.float32) / 255.0
        
        # Screen blend only the RGB channels, use overlay alpha as mix factor
        alpha = overlay[:, :, 3:4]
        blended_rgb = 1.0 - (1.0 - base[:, :, :3]) * (1.0 - overlay[:, :, :3] * alpha)
        
        result = base.copy()
        result[:, :, :3] = blended_rgb
        result = (np.clip(result, 0, 1) * 255).astype(np.uint8)
        img_rgba = Image.fromarray(result)
    
    return img_rgba.convert('RGB')

def _add_red_tint_to_faces(img: Image.Image) -> Image.Image:
    """
    Detect faces and add a red tint to face regions.
    Uses MediaPipe face detection for face bounding boxes.
    """
    mp_face_detection = mp.solutions.face_detection
    img_array = np.array(img)
    h, w = img_array.shape[:2]
    
    with mp_face_detection.FaceDetection(
        model_selection=1,
        min_detection_confidence=0.3
    ) as face_detection:
        results = face_detection.process(img_array)
        
        if not results.detections:
            return img
        
        for detection in results.detections:
            bbox = detection.location_data.relative_bounding_box
            x = max(int(bbox.xmin * w), 0)
            y = max(int(bbox.ymin * h), 0)
            bw = int(bbox.width * w)
            bh = int(bbox.height * h)
            
            # Clamp to image boundaries
            x2 = min(x + bw, w)
            y2 = min(y + bh, h)
            
            roi = img_array[y:y2, x:x2].copy()
            # Boost red channel
            roi[:, :, 0] = np.clip(roi[:, :, 0].astype(np.float32) * 1.5, 0, 255).astype(np.uint8)
            # Blend 50/50 with original
            img_array[y:y2, x:x2] = (
                (img_array[y:y2, x:x2].astype(np.float32) * 0.5 + roi.astype(np.float32) * 0.5)
            ).astype(np.uint8)
    
    return Image.fromarray(img_array)

async def deep_fry_image(img: Image.Image) -> Image.Image:
    """
    Deep fry an image with face detection, red tinting, and lens flare eyes.
    """
    try:
        # Detect eyes
        eyes = _get_eye_positions(img)
        
        # Add red tint to faces
        img = _add_red_tint_to_faces(img)
        
        # Overlay lens flare on eyes
        img = _overlay_lens_flare(img, eyes)
        
        # Apply deeppyer for additional deep frying effects
        fried_img = await deeppyer.deepfry(img, flares=False)
        return fried_img
        
    except Exception as e:
        print(f"Error in deep_fry_image: {str(e)}")
        return img

async def handle_deepfry_command(reply, message=None) -> Union[File, str]:
    """
    Deep fry an image from a replied-to message or the command message itself.
    
    Args:
        reply: The message reference (message.reference)
        message: The command message itself (for checking its own attachments)
    Returns:
        Union[File, str]: The deep-fried image as a Discord file or error message
    """
    image_attachment = None
    
    # Priority 1: Check the replied-to message
    if reply and reply.resolved and hasattr(reply.resolved, 'attachments'):
        for attachment in reply.resolved.attachments:
            if is_supported_format(attachment):
                image_attachment = attachment
                break
        
        # Check embeds on the replied-to message
        if not image_attachment:
            embeds = getattr(reply.resolved, 'embeds', [])
            for embed in embeds:
                if embed.image:
                    class MockAttachment:
                        def __init__(self, url):
                            self.url = url
                            clean_url = url.split('?')[0]
                            self.filename = clean_url.split('/')[-1]
                            self.content_type = 'image/png'
                    image_attachment = MockAttachment(embed.image.url)
                    break
    
    # Priority 2: Check the command message's own attachments
    if not image_attachment and message:
        for attachment in message.attachments:
            if is_supported_format(attachment):
                image_attachment = attachment
                break
    
    if not image_attachment:
        return "Cannot deep fry - no valid image found in the message."

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_attachment.url) as response:
                if response.status != 200:
                    return "Failed to download the image."
                image_data = await response.read()

        pil_image = await process_image(image_data)
        if pil_image is None:
            return "Failed to process the image format."

        fried_img = await deep_fry_image(pil_image)

        output = io.BytesIO()
        fried_img.save(output, format='PNG')
        output.seek(0)
        return File(output, filename='deepfried.png')

    except Exception as e:
        return f"Error deep frying image: {str(e)}"