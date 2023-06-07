import os
import random

from config import anime_path


def choose_random_anime_image():
    image_files = []
    for file_name in os.listdir(anime_path):
        if file_name.endswith((".jpg", ".jpeg", ".png")):
            img_file = os.path.join(anime_path, file_name)
            if os.path.getsize(img_file) < 10 * 1024 * 1024:
                image_files.append(img_file)

    if not image_files:
        raise ValueError("No image files found in the folder")

    random_image = random.choice(image_files)
    return random_image
