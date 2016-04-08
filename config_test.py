"""
fill in appropriate values and rename me to config.py
"""

import os

basedir = os.path.abspath(os.path.dirname(__file__))

# database info
DB_NAME = 'mastodon_test'
DB_PASSWORD = 'felix'
DB_SERVER = 'localhost'
DB_USER = 'felix'

SQLALCHEMY_DATABASE_URI = 'postgresql://{}:{}@{}/{}'.format(DB_USER, DB_PASSWORD, DB_SERVER, DB_NAME)

SQLALCHEMY_MIGRATE_REPO = os.path.join(basedir, 'db_repository')

SQLALCHEMY_TRACK_MODIFICATIONS = False
