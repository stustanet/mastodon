#!flask/bin/python
import os.path
import os
import re
import subprocess
import shutil
from config import *


def getLength(filename):
    try:
        result = subprocess.check_output(["ffprobe", "-v", "quiet",
                                          "-show_format", filename])
        m = re.search('duration=([0-9]+\.[0-9]*)', result.decode('utf-8'))
    except:
        print("ffmpeg (getLength) failed", filename)
        return 0

    if m:
        return float(m.group(1))
    return 0


def getThumb(title, filename):
    dir_path = os.path.join(PATH_TO_THUMBNAILS, title)
    print("PATH: ", dir_path)
    if os.path.exists(dir_path + ".jpg"):
        print("thumbnail exists:", title)
        return 0

    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    length = int(getLength(filename))

    # movies, tv shows
    if length > 600:
        # first thumbnail 5th minute
        start = 300
    # clips, trailer
    elif length > 30:
        start = 10
    else:
        print("getThumb: video to short:", length, title, filename)
        shutil.rmtree(dir_path)
        return -1
    step = int((length - start) / 10)

    for i in range(start, length, step):
        try:
            subprocess.check_output(["ffmpeg", "-v", "quiet", "-ss", str(i),
                                     "-i", filename, "-vf", "scale=320:-1",
                                     "-vframes", "1", "-f", "image2",
                                     dir_path+"/out-%08d.jpg" % (i)],
                                    timeout=60)
        except subprocess.TimeoutExpired:
            print("ffmpeg timeout:", title, "frame:", i)
            shutil.rmtree(dir_path)
            return -1
        except Exception:
            print("ffmpeg failed:", "frame:", i, title, filename)
            shutil.rmtree(dir_path)
            return -1

    mergeThumbs(title)

    shutil.rmtree(dir_path)


def mergeThumbs(title):
    try:
        subprocess.check_output(["convert", "+append",
                                 PATH_TO_THUMBNAILS + title +
                                 "/out-*.jpg",
                                 PATH_TO_THUMBNAILS + title + ".jpg"])
    except:
        print("convert failed:", title)
