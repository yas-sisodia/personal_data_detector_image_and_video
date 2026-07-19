

# ========================= no highlight ================================

import os
import cv2
import numpy as np
import tempfile
from PIL import Image
from skimage.metrics import structural_similarity as ssim
import asyncio

from backend.core.shared import (
    convert_text_segments,
    run_ocr_on_video,
    detect_objects_in_video,
    generate_caption,
    classify,
    analyze_text
)


# =========================================================
# Keyframe extraction
# =========================================================
def extract_keyframes(video_path, output_dir):
    cap = cv2.VideoCapture(video_path)
    ret, prev = cap.read()
    if not ret:
        return []

    prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    last_saved = None
    frames = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        sim = ssim(prev_gray, gray)
        blur = cv2.Laplacian(gray, cv2.CV_64F).var()
        motion = cv2.absdiff(prev_gray, gray).mean()

        if sim < 0.90 and blur > 120 and motion > 2.0:
            if last_saved is None or ssim(last_saved, gray) < 0.95:
                path = os.path.join(output_dir, f"frame_{len(frames):04d}.jpg")
                cv2.imwrite(path, frame)
                frames.append(path)
                last_saved = gray

        prev_gray = gray

    cap.release()
    return frames



def make_video_from_keyframe_paths(
    keyframe_paths,
    fps=60,
    codec="mp4v",
    ext=".mp4"
):
    """
    keyframe_paths: list of absolute image paths (already ordered)
    returns: temp video file path
    """

    if not keyframe_paths:
        raise ValueError("Empty keyframe list")

    # Read first frame to get dimensions
    first_frame = cv2.imread(keyframe_paths[0])
    if first_frame is None:
        raise ValueError("Failed to read first keyframe")

    height, width, _ = first_frame.shape

    # Create temp video file
    temp_file = tempfile.NamedTemporaryFile(
        suffix=ext,
        delete=False
    )
    video_path = temp_file.name
    temp_file.close()

    fourcc = cv2.VideoWriter_fourcc(*codec)
    writer = cv2.VideoWriter(
        video_path,
        fourcc,
        fps,
        (width, height)
    )

    for path in keyframe_paths:
        frame = cv2.imread(path)
        if frame is None:
            continue

        # Safety resize (in case dimensions vary)
        if frame.shape[:2] != (height, width):
            frame = cv2.resize(frame, (width, height))

        writer.write(frame)

    writer.release()
    return video_path



def build_collage(frames, output_path, num_frames=6):
    idxs = np.linspace(0, len(frames) - 1, min(num_frames, len(frames)), dtype=int)
    imgs = [cv2.resize(cv2.imread(frames[i]), (320, 180)) for i in idxs]

    while len(imgs) < num_frames:
        imgs.append(imgs[-1])

    collage = np.vstack([
        np.hstack(imgs[:3]),
        np.hstack(imgs[3:6]),
    ])

    cv2.imwrite(output_path, collage)
    return output_path


# 
# =========================================================
import base64

def image_to_base64(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# =========================================================
# 
# =========================================================


def build_video_from_frames(
    frame_paths,
    fps=2,
    size=(640, 360),
    codec="mp4v"
):
    """
    Create a video from frame image paths.
    Returns the temporary video path.
    """

    if not frame_paths:
        return None

    tmp_dir = tempfile.mkdtemp()
    video_path = os.path.join(tmp_dir, "keyframes_video.mp4")

    fourcc = cv2.VideoWriter_fourcc(*codec)
    writer = cv2.VideoWriter(video_path, fourcc, fps, size)

    for frame_path in frame_paths:
        img = cv2.imread(frame_path)
        if img is None:
            continue

        img = cv2.resize(img, size)
        writer.write(img)

    writer.release()
    return video_path




# =========================================================
# Video pipeline
# =========================================================



async def run_video_pipeline(video_path, progress_cb=None, enable_caption=False):

    async def emit(step: str, percent: int, data=None):
        if progress_cb:
            await progress_cb(step, percent, data)

    data = {
        "sequence": None,
        "caption": None,
        "text": None,
        "objects": None,
        "labels": None,
        "scores": None,
        "textSeg": None,
        "caption_image": None,
    }

    with tempfile.TemporaryDirectory() as tmp:

        # -----------------------------------
        # Extract keyframes
        # -----------------------------------
        await emit("Extracting keyframes", 10, data)
        # keyframes = extract_keyframes(video_path, tmp)
        keyframes = await asyncio.to_thread(
    extract_keyframes,
    video_path,
    tmp,
)

        # -----------------------------------
        # Build collage
        # -----------------------------------
        await emit("Building context collage", 25, data)
        # collage_path = build_collage(keyframes, os.path.join(tmp, "context.jpg"))/
        collage_path = await asyncio.to_thread(
    build_collage,
    keyframes,
    os.path.join(tmp, "context.jpg"),
)
        collage_base64 = image_to_base64(collage_path)
        data["caption_image"] = collage_base64

        # -----------------------------------
        # Rebuild temp video from keyframes
        # -----------------------------------
        await emit("Rebuilding video from keyframes", 35, data)
        # video_path = make_video_from_keyframe_paths(
        #     keyframe_paths=keyframes,
        #     fps=60
        # )
        video_path = make_video_from_keyframe_paths(
    keyframe_paths=keyframes,
    fps=60
)

        # -----------------------------------
        # OCR
        # -----------------------------------
        await emit("Running OCR on video", 45, data)
        # textInVideo = run_ocr_on_video(video_path)
        textInVideo = await asyncio.to_thread(
    run_ocr_on_video,
    video_path,
)
        textSeg = analyze_text(textInVideo)

        data["text"] = textInVideo
        data["textSeg"] = convert_text_segments(textSeg)

        # -----------------------------------
        # Object Detection (separated step)
        # -----------------------------------
        await emit("Detecting objects in video", 55, data)
        # objectsInVideo = detect_objects_in_video(video_path)
        objectsInVideo = await asyncio.to_thread(
    detect_objects_in_video,
    video_path,
)
        data["objects"] = objectsInVideo

        # -----------------------------------
        # Caption
        # -----------------------------------
        caption = ""
        await emit("Generating video caption", 70, data)
        if enable_caption:
            # caption = generate_caption(collage_path)
            caption = await asyncio.to_thread( generate_caption,collage_path,)
        data["caption"] = caption


        # -----------------------------------
        # Classification
        # -----------------------------------
        await emit("Final sensitivity classification", 90, data)

        merged_text = f"{textInVideo}\n{objectsInVideo}\n{caption}"
        # classification = classify(merged_text)
        classification = await asyncio.to_thread(
    classify,
    merged_text,
)

        data["sequence"] = merged_text
        data["labels"] = classification["labels"]
        data["scores"] = classification["scores"]

        await emit("Completed", 100, data)

        return data































