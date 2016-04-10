#!venv/bin/python
# encoding=utf8

import sys
import os
from api.models import Media, get_or_create_category
from api import db
import thumbs
import binascii
from config import PATH_TO_MOUNT, URL_TO_MOUNT, INDEX_FOLDER, VIDEO_CATEGORY_RULES
import hashlib
import mimetypes
import time
import re
import videoinfo
import logging
import traceback
from concurrent.futures import ProcessPoolExecutor


def get_files():
    """\
    returns a list of tuples of filename, mimetype and last modified date of all relevant files in root directory
    """

    last_update = 0
    l = 0

    lis = []

    search_path = os.path.join(PATH_TO_MOUNT, INDEX_FOLDER)
    logging.debug("search_path: {}".format(search_path))
    for root, dirs, files in os.walk(search_path):
        for filename in files:
            (full_mime, encoding) = mimetypes.guess_type(filename)
            mime = None

            if full_mime:
                mime = full_mime.split("/")[0]

            if mime in ["video", "audio", "image"]:
                filepath = os.path.join(root, filename)
                try:
                    lastModified = os.path.getmtime(filepath)
                    lis.append((os.path.relpath(filepath, PATH_TO_MOUNT), full_mime, int(lastModified)))
                    l = l + 1

                    if time.time() - last_update > 5:
                        last_update = time.time()
                        logging.info("Getting files in FS: {}".format(l))

                except os.error as err:
                    msg = "Error when accessing file '{}' in folder '{}':".format(filename, root)
                    logging.error(msg)

    return lis


def get_files_in_db():
    """\
    returns a list of tuples of filename, mimetype and last modified date of all files currently indexed in the db
    """

    medias = Media.query.all()
    lis = []

    for media in medias:
        lis.append((media.path, media.mimetype, media.lastModified))

    return lis


def get_deltas(database_files, filesystem_files):
    """\
    takes a list of all files currently indexed and a list of all files available in the filesystem_filesystem
    returns two lists one with files to create/update in the db and one with files to be deleted from the db
    """
    # extract all paths for easy matching in the for loops
    database_paths = [relativePath for (relativePath, _, _) in database_files]
    filesystem_paths = [relativePath for (relativePath, _, _) in filesystem_files]

    to_upsert = []
    to_delete = []

    for f in database_files:
        (relativePath, _, _) = f
        # relativePath is indexed in db but no longer available in FS
        if relativePath not in filesystem_paths:
            to_delete.append(f)

    for f in filesystem_files:
        (relativePath, mime, currentLastModified) = f
        # file in FS which is not indexed at all
        if relativePath not in database_paths:
            to_upsert.append(f)
        # file is already in database, check if it needs to be updated
        else:
            # get info about indexed file to check wether it has changed
            dbF = [f for f in database_files if f[0] == relativePath][0]
            indexedLastModifed = dbF[2]

            if indexedLastModifed != currentLastModified:
                # a indexed file that should be updated in the DB is first deleted then
                # added as if it was never indexed. just adding it to "to_delete" here makes the logic in main
                # very simple
                to_delete.append(dbF)
                to_upsert.append(f)

    return (to_upsert, to_delete)


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

def async_index_medium(relativePath, mime, lastModified):
    """\
    Takes three arguments path, mime, lsatModified(directly from get_deltas)
    And does all operations to index the medium:

    - calculate sha
    - insert into db
    - create thumbnail

    This function can be used in multiprocessing Pools because it doesn't depend on any
    global variables.
    It will create its own DB Connection
    """

    logging.info("Indexing {}".format(relativePath))

    # get a custom instance of db
    #from api import db

    path = os.path.join(PATH_TO_MOUNT, relativePath)
    logging.info("Indexing 2 {}".format(relativePath))

    sha = hashfile(open(path, "rb"), hashlib.sha256())
    logging.info("Indexing 3 {}".format(relativePath))

    mediainfo = videoinfo.ffprobe(path)
    duration = 0
    if "format" in mediainfo and "duration" in mediainfo["format"]:
        duration = float(mediainfo["format"]["duration"])

    m = Media(
        path=relativePath,
        category=get_or_create_category(categorize(relativePath, mime, duration)),
        mediainfo=mediainfo,
        lastModified=lastModified,
        mimetype=mime,
        timeLastIndexed=int(time.time()),
        sha=sha)

    try:
        db.session.add(m)
        db.session.commit()
    except:
        logging.error("Error adding new media to DB: {}".format(sys.exc_info()[0]))

    if mime.startswith("video"):
        try :
             thumbs.getThumb(binascii.hexlify(m.sha).decode(), os.path.join(PATH_TO_MOUNT, m.path))
        except:
            logging.warning("Error generating thumb: {}".format(sys.exc_info()))

    logging.info("Finished indexing {}".format(relativePath))

def main():
    with ProcessPoolExecutor() as executor:
        logging.basicConfig(level=logging.DEBUG)

        logging.info("Scraper started.")
        logging.info("Getting files in DB.")
        database_files = get_files_in_db()
        logging.info("Files in DB: {}".format(len(database_files)))

        filesystem_files = get_files()
        logging.info("Getting files in FS: {}".format(len(filesystem_files)))

        (to_upsert, to_delete) = get_deltas(database_files, filesystem_files)

        logging.info("{} to update/insert, {} to delete".format(len(to_upsert), len(to_delete)))

        for (relativePath, _, _) in to_delete:
            Media.query.filter_by(path=relativePath).delete()

        db.session.commit()

        num_to_upsert = len(to_upsert)

        for (relativePath, mime, lastModified) in to_upsert:
            #executor.submit(async_index_medium, relativePath, mime, lastModified)
            async_index_medium(relativePath, mime, lastModified)

        executor.shutdown(wait=False)

if __name__ == "__main__":
    main()
