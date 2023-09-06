import os
import random

from config import slap_path


def choose_random_slap_gif():
    gif_files = []
    for file_name in os.listdir(slap_path):
        if file_name.endswith(".gif"):
            gif_file = os.path.join(slap_path, file_name)
            if os.path.getsize(gif_file) < 10 * 1024 * 1024:
                gif_files.append(gif_file)

    if not gif_files:
        raise ValueError("No gif files found in the folder")

    random_gif = random.choice(gif_files)
    return random_gif
