#!flask/bin/python
import os.path
import os
import re
import subprocess
import shutil
from config import *
import logging
import sys

def getLength(filename):
    try:
        result = subprocess.check_output(["ffprobe", "-v", "quiet",
                                          "-show_format", filename])
        m = re.search('duration=([0-9]+\.[0-9]*)', result.decode('utf-8'))
    except:
        logging.warning("ffmpeg (getLength) failed {}".format(filename))
        return None

    if m:
        return int(m.group(1))

    return None


def generateThumb(title, filename):
    dir_path = os.path.join(PATH_TO_THUMBNAILS, title)
    if os.path.exists(dir_path + ".jpg"):
        return

    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    length = getLength(filename)
    if not length:
        return

    # movies, tv shows
    if length > 600:
        # first thumbnail 5th minute
        start = 300
    # clips, trailer
    elif length > 30:
        start = 10
    else:
        shutil.rmtree(dir_path)
        return

    step = int((length - start) / 10)

    for i in range(start, length, step):
        try:
            subprocess.check_output(["ffmpeg", "-v", "quiet", "-ss", str(i),
                                     "-i", filename, "-vf", "scale=320:-1",
                                     "-vframes", "1", "-f", "image2",
                                     dir_path+"/out-%08d.jpg" % (i)],
                                    timeout=60)
        except subprocess.TimeoutExpired:
            logging.warning("ffmpeg timeout: {} frame: {}".format(title, i))
            shutil.rmtree(dir_path)
            return

        except Exception:
            logging.warning("ffmpeg failed: {} {} frame: {}".format(i, title, filename))
            shutil.rmtree(dir_path)
            return

    mergeThumbs(title)

    shutil.rmtree(dir_path)


def mergeThumbs(title):
    try:
        in_path = os.path.join(PATH_TO_THUMBNAILS ,title, "out-*.jpg")
        out_path = os.path.join(PATH_TO_THUMBNAILS, title + ".jpg")
        subprocess.check_output(["convert", "+append", in_path, out_path])
    except:
        logging.warning("convert failed: {}".format(title))
