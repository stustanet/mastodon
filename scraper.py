#!venv/bin/python
# encoding=utf8

import sys
import os
from api import db
from api.models import Media, get_or_create_category
import thumbs
import binascii
from config import PATH_TO_MOUNT, URL_TO_MOUNT, INDEX_FOLDER, VIDEO_CATEGORY_RULES, SQLALCHEMY_DATABASE_URI
import hashlib
import mimetypes
import time
import re
import videoinfo
import logging
import traceback

NO_OF_FILES_TO_INDEX = 1000

def get_files_in_db():
    """\
    returns a list of tuples of filename, mimetype and last modified date of all files currently indexed in the db
    """

    medias = Media.query.all()
    lis = []

    for media in medias:
        lis.append((media.path, media.mimetype, media.lastModified))

    return lis

def get_not_in_db(filesystem_files):
    lis = []
    for f in filesystem_files:
        if not Media.query.filter(Media.path == f[0]).first():
            lis.append(f)
    return lis

def hashfile(afile, hasher, blocksize=65536):
    buf = afile.read(blocksize)
    while len(buf) > 0:
        hasher.update(buf)
        buf = afile.read(blocksize)
    return hasher.digest()

def categorize(path, mime, duration):
    """\
    takes a relative path on mammut and returnes one of the category constants in api/constants
    """
    category = None

    if mime.startswith("music"):
        category = "music"

    elif mime.startswith("image"):
        category = "image"

    else:
        for c, rules in VIDEO_CATEGORY_RULES.items():
            for rule in rules:
                if re.match(rule, path, re.IGNORECASE):
                    category = c
                    break

            if category:
                break

        if not category and duration > 4200:
            category = "movie"
        elif not category:
            category = "uncategorized"

    return category

def index_medium(relativePath, mime, lastModified):
    """\
    Takes three arguments path, mime, lsatModified(directly from get_deltas)
    And does all operations to index the medium:

    - calculate sha
    - insert into db
    - create thumbnail
    """

    logging.info("Indexing {}".format(relativePath))

    # get a custom instance of db #from api import db

    path = os.path.join(PATH_TO_MOUNT, relativePath)

    sha = hashfile(open(path, "rb"), hashlib.sha256())

    mediainfo = videoinfo.ffprobe(path)
    duration = 0
    if "format" in mediainfo and "duration" in mediainfo["format"]:
        duration = float(mediainfo["format"]["duration"])
    category = categorize(relativePath, mime, duration)

    m = Media(
        path=relativePath,
        mediainfo=mediainfo,
        lastModified=lastModified,
        category=get_or_create_category(category),
        mimetype=mime,
        timeLastIndexed=int(time.time()),
        sha=sha)

    return m

def hash_and_add(filesystem_files):
    new_files = get_not_in_db(filesystem_files)
    for f, mime, lm  in new_files:
        m = index_medium(f, mime, lm)
        db.session.add(m)
        db.session.commit()

def main():
    # Collect files until NO_OF_FILES_TO_INDEX reached
    # then check if in DB, if not index
    logging.basicConfig(level=logging.DEBUG)
    lis = []
    search_path = os.path.join(PATH_TO_MOUNT, INDEX_FOLDER)
    logging.debug("search_path: {}".format(search_path))
    counter = 0
    for root, dirs, files in os.walk(search_path):
        for filename in files:
            (full_mime, encoding) = mimetypes.guess_type(filename)
            mime = None

            if full_mime:
                mime = full_mime.split("/")[0]

            if mime in ["video", "audio", "image", "text"]:
                filepath = os.path.join(root, filename)
                try:
                    lastModified = os.path.getmtime(filepath)
                    lis.append((os.path.relpath(filepath, PATH_TO_MOUNT), full_mime, int(lastModified)))
                    if len(lis) % NO_OF_FILES_TO_INDEX == 0:
                        logging.info("Checking files {}-{}".format(counter * NO_OF_FILES_TO_INDEX, (counter + 1) * NO_OF_FILES_TO_INDEX))
                        logging.info("Last file: {}".format(filepath))
                        hash_and_add(lis)
                        lis = []
                        counter = counter + 1

                except os.error as err:
                    msg = "Error when accessing file '{}' in folder '{}':".format(filename, root)
                    logging.error(msg)
    hash_and_add(lis)

if __name__ == "__main__":
    main()

