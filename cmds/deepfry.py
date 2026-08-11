import io
import asyncio
from discord import File, Embed
from PIL import Image
import numpy as np
import deeppyer
import os
from typing import Optional, Union

import mediapipe as mp
from ui_utils import error_embed, warning_embed, extract_image_url, fetch_image_bytes

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
        data[:,:,2] = (data[:,:,2] * 0.3).astype(np.uint8)  # Suppress blue
        return Image.fromarray(data)
    except Exception as e:
        print(f"Error loading lens flare: {e}")
        return None

def _process_image_bytes(image_data: bytes) -> Optional[Image.Image]:
    """Process image data into a PIL Image, handling different formats (run in thread pool)."""
    try:
        img = Image.open(io.BytesIO(image_data))
        
        if img.format == 'GIF' and getattr(img, 'is_animated', False):
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
        print(f"Error processing image bytes: {str(e)}")
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

def _process_deepfry_sync(img: Image.Image) -> Image.Image:
    """Synchronous CPU-bound image processing: face mesh, face tint, and lens flare."""
    try:
        # Detect eyes with MediaPipe FaceMesh
        eyes = _get_eye_positions(img)
        # Add red tint to faces with MediaPipe FaceDetection
        img = _add_red_tint_to_faces(img)
        # Overlay lens flare on eyes
        img = _overlay_lens_flare(img, eyes)
        return img
    except Exception as e:
        print(f"Error in _process_deepfry_sync: {str(e)}")
        return img

def _save_image_to_bytes(img: Image.Image) -> io.BytesIO:
    """Synchronous PNG compression of PIL image into BytesIO buffer."""
    output = io.BytesIO()
    img.save(output, format='PNG')
    output.seek(0)
    return output

async def deep_fry_image(img: Image.Image) -> Image.Image:
    """
    Deep fry an image with face detection, red tinting, and lens flare eyes.
    Offloads heavy MediaPipe inference and array transforms to a background thread.
    """
    try:
        # Run CPU-bound MediaPipe detection and lens flare overlay in worker thread
        img = await asyncio.to_thread(_process_deepfry_sync, img)
        
        # Apply deeppyer for additional deep frying effects
        fried_img = await deeppyer.deepfry(img, flares=False)
        return fried_img
        
    except Exception as e:
        print(f"Error in deep_fry_image: {str(e)}")
        return img

async def handle_deepfry_command(reply, message=None) -> Union[File, Embed]:
    """
    Deep fry an image from a replied-to message or the command message itself.
    """
    image_url = extract_image_url(reply, message)
    if not image_url:
        return warning_embed("Cannot deep fry — no valid image found in the message or attachment.", title="⚠️ Image Not Found")

    try:
        image_data, error_msg = await fetch_image_bytes(image_url)
        if error_msg or not image_data:
            return error_embed(error_msg or "Failed to download the image.")

        pil_image = await asyncio.to_thread(_process_image_bytes, image_data)
        if pil_image is None:
            return error_embed("Failed to process the image format.")

        fried_img = await deep_fry_image(pil_image)

        output = await asyncio.to_thread(_save_image_to_bytes, fried_img)
        return File(output, filename='deepfried.png')

    except Exception as e:
        return error_embed(f"Error deep frying image: {str(e)}", title="❌ Deepfry Error")