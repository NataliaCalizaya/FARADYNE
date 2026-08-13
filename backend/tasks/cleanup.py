from core.config import settings
import os
import time

def cleanup_temp_files():
    now = time.time()
    for filename in os.listdir(settings.UPLOAD_DIR):
        filepath = os.path.join(settings.UPLOAD_DIR, filename)
        if os.stat(filepath).st_mtime < now - 24 * 3600:
            if os.path.isfile(filepath):
                os.remove(filepath)
