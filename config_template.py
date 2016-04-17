"""
fill in appropriate values and rename me to config.py
"""

import os

basedir = os.path.abspath(os.path.dirname(__file__))

# database info
DB_NAME = "CHANGEME"
DB_PASSWORD = "CHANGEME"
DB_SERVER = "CHANGEME"
DB_USER = "CHANGEME"

SQLALCHEMY_DATABASE_URI = "postgresql://{}:{}@{}/{}".format(DB_USER, DB_PASSWORD, DB_SERVER, DB_NAME)

SQLALCHEMY_MIGRATE_REPO = os.path.join(basedir, "db_repository")

SQLALCHEMY_TRACK_MODIFICATIONS = False

URL_TO_MOUNT = ""
# PATH_TO_MOUNT should be public mammut's root folder
PATH_TO_MOUNT = ""
INDEX_FOLDER = [""]

THUMBNAIL_ROOT_URL = ""
PATH_TO_THUMBNAILS = ""

# dict with category name as key and an array of regex rules video paths belonging to this category have to match
VIDEO_CATEGORY_RULES = {}

# if there is a series category (configured in VIDEO_CATEGORY_RULES) it can be entered here to run the metadata guesser just on media with this category
# if it is None the metadata guesser is ran on all uncategorized video files
VIDEO_CATEGORY_SERIES = None

# if VIDEO_CATEGORY_MOVIES and VIDEO_CATEGORY_MOVIES_DURATION is set
# all media not categorized by VIDEO_CATEGORY_RULES with a duration greater or equal than VIDEO_CATEGORY_MOVIES_DURATION
# gets the category VIDEO_CATEGORY_MOVIES
VIDEO_CATEGORY_MOVIES = "Movie"
VIDEO_CATEGORY_MOVIES_DURATION = 4200

IMAGES_CATEGORY = "Images"
MUSIC_CATEGORY = "Music"
