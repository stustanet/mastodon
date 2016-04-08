#!flask/bin/python
# encoding=utf8

import sys
import fnmatch
import os
import urllib
from datetime import datetime
from app2.models import Video
from app2 import db
from config import PATH_TO_MOUNT, URL_TO_MOUNT, INDEX_FOLDERS
from videoinfo import video_info
import hashlib


def get_files(paths):
    """\
    takes a list of tuples containig filepaths and categories as argument
    and returns a list of tuples with(filename, path, category) of all mp4
    files in that directories
    """
    lis = []
    for path in paths:
        abspath = os.path.join(PATH_TO_MOUNT, path[0])
        for root, dirs, files in os.walk(abspath):
            for filename in files:
                if fnmatch.fnmatch(filename, '*.mp4'):
                    filepath = os.path.join(root, filename)
                    lis.append((os.path.relpath(filepath, PATH_TO_MOUNT),
                                path[1]))
    return lis


def collect_meta(namecat):
    """\
    takes a tuple of (filename, category) and returns all necessary metadata
     in a tuple
    """
    path = namecat[0]
    abspath = os.path.join(PATH_TO_MOUNT, path)
#    print(abspath)
    url = urllib.parse.urljoin(URL_TO_MOUNT, path)
    category = namecat[1]
    vinfo = video_info(abspath)
    title = os.path.splitext(os.path.basename(path))[0]

    return (title, path, url, category, vinfo["duration"],
            vinfo["vwidth"], vinfo["vheight"], vinfo["vcodec"],
            vinfo["acodec"], )


def write_to_db(info, pathhash):
    db.session.add(Video(id=pathhash, title=info[0], path=info[1],
                         url=info[2], category=info[3], duration=info[4],
                         vwidth=info[5], vheight=info[6], vcodec=info[7],
                         acodec=info[8], timestamp=datetime.now(),
                         blacklisted=False, thumbnail=False))
    try:
        db.session.commit()
    except:
        print('Failed to commit DB:', pathhash, info[0])


def main():
    print("Getting file list, pls grab a cup of coffee...")
    lis = get_files((INDEX_FOLDERS))

    for i in lis:
        pathhash = hashlib.sha256(i[0].encode()).hexdigest()
        q = db.session.query(Video).filter(Video.id == pathhash)
        # FIXME
        if q.count() == 0:
            info = collect_meta(i)
            write_to_db(info, pathhash)
            print("Added to DB:\t", pathhash, i[0])
        else:
            print("Is already in DB:\t", pathhash, i[0])

if __name__ == "__main__":
    main()
