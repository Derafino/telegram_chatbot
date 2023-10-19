import os
import random

from PIL import Image

from config import img_path, logger

max_size_bytes = 10 * 1024 * 1024
max_total_pixels = 10000
max_ratio = 20


def is_valid_photo(photo_path):
    import os

    if os.path.getsize(photo_path) > max_size_bytes:
        print("Caution: The photo must be at most 10MB in size.")
        return False

    # Check photo dimensions
    from PIL import Image

    with Image.open(photo_path) as img:
        width, height = img.size
        total_dimensions = width + height
        width_height_ratio = max(width, height) / min(width, height)

        if total_dimensions > max_total_pixels:
            print("Caution: The photo’s width and height must not exceed 10000 in total.")
            return False

        if width_height_ratio > max_ratio:
            print("Caution: Width and height ratio must be at most 20.")
            return False

    return True


def compress_image(input_path, output_path, quality=100):
    img = Image.open(input_path)

    original_width, original_height = img.size
    original_ratio = original_width / original_height

    if original_width + original_height > max_total_pixels or original_ratio > max_ratio:
        new_width, new_height = original_width, original_height
        while (new_width + new_height > max_total_pixels) or (new_width / new_height > max_ratio):
            new_width = int(new_width * 0.9)
            new_height = int(new_height * 0.9)
        img = img.resize((new_width, new_height), Image.LANCZOS)

    img.save(output_path, optimize=True, quality=quality)
    while os.path.getsize(output_path) > max_size_bytes:
        quality -= 5
        img.save(output_path, optimize=True, quality=quality)


def choose_random_image():
    image_files = []
    for file_name in os.listdir(img_path):
        if file_name.endswith((".jpg", ".jpeg", ".png")):
            img_file = os.path.join(img_path, file_name)
            if os.path.getsize(img_file) < 10 * 1024 * 1024:
                image_files.append(img_file)

    if not image_files:
        raise ValueError("No image files found in the folder")

    random_image = random.choice(image_files)
    if is_valid_photo(random_image):
        logger.debug("The input photo is already valid.")
    else:
        logger.debug("Making the input photo valid...")
        compress_image(random_image, random_image)
        logger.debug(f"Valid photo saved at {random_image}")

    return random_image
