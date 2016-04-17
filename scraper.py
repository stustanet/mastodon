#!venv/bin/python
# encoding=utf8

import sys
import os
from api import db
from api.models import Media, get_or_create_category
from sqlalchemy.orm import joinedload
import thumbs
import binascii
from config import PATH_TO_MOUNT, URL_TO_MOUNT, INDEX_FOLDER, VIDEO_CATEGORY_RULES
import config
import hashlib
import mutagen
import guessit
import mimetypes
import time
import re
import videoinfo
import logging
import traceback
import concurrent.futures
from multiprocessing import Process, cpu_count, Queue


def get_files(search_path, mount_path):
    """\
    returns a list of tuples of filename, mimetype and last modified date of all relevant files in root directory
    """

    last_update = 0
    l = 0

    lis = []

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

                    lis.append({"path": os.path.relpath(filepath, mount_path),
                        "mime": full_mime, "lastModified": lastModified, "fullpath": filepath})

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
        lis.append({"path": media.path, "mime": media.mimetype,
            "lastModified": media.lastModified, "sha": media.sha})

    return lis

# function for executor.map needs to be pickable? and therefore at the top level?
def get_sha(f):
    if not "sha" in f:
        f["sha"] = hashfile(f["fullpath"])
    return f

def get_deltas(database_files, filesystem_files):
    """\

    """
    # TODO/FIXME: This function proibably needs lots of memory (gigabytes) when running on big folders
    # (~ 800k files on mammut * (~150 path + 32 sha + ~10 mime + 4 last modifed) ~= 160 MB )
    # (dictionaries need space for every element + space for every key + space for actual data)
    #
    # - without rename-detection detecting new files could run recursively on each folder
    # - detecting deleted files could get the objects from the DB lazily and use os.path.exists
    # - rename detection could be limited to the top folder (a_yyyyyyy_xxx, 00xxxx)
    #   (but this is mammut specific and hardly configurable)
    #
    # - another possibility would be to store the information this function needs in a small temporary database (SQLite?)
    #   - even this database in memory would probably reduce memory usage a little. I would image that
    #     e.g. SQLite could store path, mime, lastMOdified and sha more efficient than python does
    #   - lookups would probably be faster than "path in filesystem_paths"

    # extract information for easy and fast access
    # TODO/FIXME: Again this is optimized for speed but uses much more memory
    # real world tests are need to find out which is the bottleneck, CPU or memory
    database_files_lookup = {f["path"]:f for f in database_files}
    filesystem_files_lookup = {f["path"]:f for f in filesystem_files}

    for filesystem_file in filesystem_files:
        if filesystem_file["path"] in database_files_lookup:
            filesystem_file["sha"] = database_files_lookup[filesystem_file["path"]]["sha"]

    # calculate sha sums of all unknown filenames concurrently

    logging.info("Calculating SHA256 sums...")
    with concurrent.futures.ProcessPoolExecutor() as executor:
        filesystem_files = executor.map(get_sha, filesystem_files)


    # lists that get returned
    to_insert = []
    renamed = []
    content_changed = []
    to_delete = []

    deleted_or_renamed = {}

    for f in database_files:
        # relativePath is indexed in db but no longer available in FS
        if f["path"] not in filesystem_files_lookup:
            deleted_or_renamed[f["sha"]] = f

    for f in filesystem_files:
        # file in FS which seems not indexed at all (we don't know yet if it was renamed)
        if f["path"] not in database_files_lookup:
            # if file was renamed there has to be a file which seems deleted but has the same hash
            if f["sha"] in deleted_or_renamed:
                f["renamed_from"] = deleted_or_renamed[f["sha"]]["path"]
                print(f["renamed_from"], "->", f["path"])
                renamed.append(f)
                del deleted_or_renamed[f["sha"]]

            # there is no corresponding deleted file for this new file ==> insert as new
            else:
                print("new", f["path"])
                to_insert.append(f)

        # file is already in database, check if it changed
        else:
            if database_files_lookup[f["path"]]["lastModified"] != f["lastModified"]:
                print(f["path"], "changed", database_files_lookup[f["path"]]["lastModified"], "->", f["lastModified"])
                f["sha"] = hashfile(f["fullpath"])
                content_changed.append(f)

    # we deleted all files which were just renamed from this dict in the previous loop
    # all thats left now are files that really got deleted
    to_delete = [f for _, f in deleted_or_renamed.items()]

    return (to_insert, to_delete, renamed, content_changed)


def hashfile(path):
    with open(path, "rb") as afile:
        hasher=hashlib.sha256()
        buf = afile.read(65536)
        while buf:
            hasher.update(buf)
            buf = afile.read(65536)
        return hasher.digest()

def categorize(path, mime, duration):
    """\
    takes a path, mime type and duration and tries to categorize the medium based on rules in VIDEO_CATEGORY_RULES
    the rules in VIDEO_CATEGORY_RULES should be tuples of the form (<category name>, <regex>)
    rules are matched from lower indexes to higher indexes
    the category corresponding to the first rule that matches is returned
    """
    category = None

    if mime.startswith("audio"):
        category = config.MUSIC_CATEGORY

    elif mime.startswith("image"):
        category = config.IMAGES_CATEGORY

    else:
        for c, rules in VIDEO_CATEGORY_RULES.items():
            for rule in rules:
                if re.match(rule, path, re.IGNORECASE):
                    category = c
                    break

            if category:
                break

        if not category and duration > config.VIDEO_CATEGORY_MOVIES_DURATION:
            category = config.VIDEO_CATEGORY_MOVIES
        elif not category:
            category = "uncategorized"

    return category


def get_metadata(path, category):
    """\
    Takes an Media object as an argument and tries to figure out metadata from the filename and the file itself

        - on media with the category MUSIC_CATEGORY metadata is read from the ID3 tag
        - on media with the category VIDEO_CATEGORY_MOVIES and VIDEO_CATEGORY_SERIES metadata is tried to guess from the filename
          using the guessit library
    """
    metadata = {}

    def conditional_copy(keys, f, to):
        for key in keys:
            if f and key in f:
                to[key] = f[key]

    if category == config.MUSIC_CATEGORY:
        try:
            info = mutagen.File(os.path.join(PATH_TO_MOUNT, path), easy=True)
            conditional_copy(["date", "discnumber", "albumartist", "tracktotal", "genre", "album", "tracknumber", "title", "artist"], info, metadata)
            for key, value in metadata.items():
                if type(value) is list:
                    metadata[key] = value[0]
        except:
            logging.info("Mutagen exception: " + str(sys.exc_info()) + " on file " + path)

    elif category in [config.VIDEO_CATEGORY_MOVIES, config.VIDEO_CATEGORY_SERIES]:
        try:
            # use just the filename and the lowest folder name
            name = os.path.split(path)[1]
            # if the path has more than 2 parts, take the one before the last one
            if os.path.split(os.path.split(path)[1])[0] != "":
                name = name + os.path.split(os.path.split(path)[1])[0]

            guess = guessit.guessit(name, options={"name_only": True})

            if medium.category.name == config.VIDEO_CATEGORY_MOVIES:
                conditional_copy(["title"], guess, metadata)

            elif medium.category.name == config.VIDEO_CATEGORY_SERIES:
                conditional_copy(["title", "episode_title", "season", "episode"], guess, metadata)
        except:
            logging.info("Guessit exception: " + str(sys.exc_info()) + " on file " + path)


    return metadata

# metadata is stored twice: the metadata dervice by get_metadata and the "overrides" by users
# this way when the get_metadata is run at a later time and there is new metadata
# the user entered metadata can take precedence. just the values which weren't overriden by users will be updated/added
def merge_metadata(current, new):
    # Hmm, I imaged this to need more logic...
    r = {"from_file": new}
    if current and "user" in current:
        r["user"] = current["user"]
    return r


def mediainfo_thumb_metadata(m):
    path = os.path.join(PATH_TO_MOUNT, m.path)
    mediainfo = videoinfo.ffprobe(path)

    if m.mimetype.startswith("video"):
        try :
            thumbs.generateThumb(binascii.hexlify(m.sha).decode(), path)
        except:
            logging.warning("Error generating thumb: {}".format(sys.exc_info()))

    duration = 0
    if "format" in mediainfo and "duration" in mediainfo["format"]:
        duration = float(mediainfo["format"]["duration"])

    category = None
    if m.category:
        category = m.category.name
    else:
        category = categorize(m.path, m.mimetype, duration)

    metadata = merge_metadata(m.meta, get_metadata(m.path, category))

    return (mediainfo, metadata)


def apply_deltas_to_db(deltas):
    to_insert, to_delete, renamed, changed = deltas


    # Delete deleted files
    for f in to_delete:
        Media.query.filter_by(path=f["path"]).delete()

    # insert:
    # - insert basic info in db
    # - mediainfo
    # - categorize
    # - thumbnail
    # - metadata

    # renamed:
    # - change path in db
    # - update lastModified in db
    # - recategorize

    # changed:
    # - change sha in db
    # - change lastModified in db
    # - change lastIndexed in db
    # - mediainfo
    # - thumbnail
    # - metadata

    # PIPELINE: basic info -> mediainfo -> thumbnails -> metadata
    insert_update = []

    # first prepare completely new media
    for f in to_insert:
        insert_update.append(Media(
            path=f["path"],
            sha=f["sha"],
            timeLastIndexed=time.time(),
            lastModified=f["lastModified"],
            mimetype=f["mime"]
            ))

    # add changed ones
    for f in changed:
        # joinedload because the subprocesses need this information but can't lazy load it
        prev = Media.query.filter_by(path=f["path"]).options(joinedload("category")).first()
        if not prev:
            logging.warning("File marked as changed is not in DB: " + f["path"])
        else:
            prev.sha = f["sha"]
            prev.lastModified = f["lastModified"]
            prev.timeLastIndexed = time.time()
            insert_update.append(prev)

    # get mediainfo, generate thumbnail and get metadata (new and changed)
    with concurrent.futures.ProcessPoolExecutor() as executor:
        mediainfo_and_metadata = zip(insert_update, executor.map(mediainfo_thumb_metadata, insert_update))

        # media object needs to be updated in the main process with an active session
        for (m, (mediainfo, metadata)) in mediainfo_and_metadata:
            m.mediainfo = mediainfo
            m.meta = metadata


    to_recategorize = []
    # just one step left: categorization. add the renamed ones (they need recategorization)
    for f in renamed:
        m = Media.query.filter_by(path=f["renamed_from"]).first()
        if not m:
            logging.warning("Marked as renamed but not in DB: {} -> {}".format(f["renamed_from"], f["path"]))
        else:
            m.path = f["path"]
            m.lastModified = f["lastModified"]
            to_recategorize.append(m.path)
            insert_update.append(m)

    # now do categorization (new and renamed)
    # TODO: Maybe move multiprocess this (probably not needed)
    def categorize_db(m):
        if not m.category or m.path in to_recategorize:
            duration = 0
            if "format" in m.mediainfo and "duration" in m.mediainfo["format"]:
                duration = float(m.mediainfo["format"]["duration"])

            m.category = get_or_create_category(categorize(m.path, m.mimetype, duration))

        return m

    insert_update = map(categorize_db, insert_update)

    # last but not least persist all changes
    for m in insert_update:
        db.session.add(m)

    db.session.commit()

def main():
    logging.basicConfig(level=logging.DEBUG)

    logging.info("Scraper started.")


    logging.info("Getting files in DB.")
    database_files = get_files_in_db()
    logging.info("Files in DB: {}".format(len(database_files)))
    filesystem_files = []

    for folder in INDEX_FOLDER:

        logging.info("Getting files in FS.")
        filesystem_files = filesystem_files +  get_files(os.path.join(PATH_TO_MOUNT, folder), PATH_TO_MOUNT)
        logging.info("Files in FS: {}".format(len(filesystem_files)))

    deltas = get_deltas(database_files, filesystem_files)

    logging.info("{} to insert, {} to delete, {} changed, {} renamed"
        "".format(len(deltas[0]), len(deltas[1]), len(deltas[2]), len(deltas[3])))

    apply_deltas_to_db(deltas)

# Go through every file and get metadata
# This is useful if the function for gathering metadata was refined
# Only overwrites metadata if the current data wasn't set by users
def metadata():
    logging.basicConfig()
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
    c = Media.query.count()
    i = 1
    for m in Media.query.all():
        print("{}/{}".format(i, c))

        metadata = get_metadata(m.path, m.category.name)
        m.metadata = merge_metadata(m.metadata, metadata)
        db.session.add(m)

        i = i + 1

    db.session.commit()



if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "metadata":
        metadata()
    else:
        main()

