from api import db
from guessit import guessit
from sqlalchemy.dialects import postgresql
from sqlalchemy import ForeignKey, Column, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import bindparam
from sqlalchemy_searchable import make_searchable, SearchQueryMixin, search
from sqlalchemy_utils.types import TSVectorType
from flask_sqlalchemy import BaseQuery
import urllib
from config import URL_TO_MOUNT, THUMBNAIL_ROOT_URL
import binascii
import logging
import os
from flask import jsonify, url_for
import json

make_searchable()

# These queries search in the mediainfo JSON which looks like this
# {"streams" : [{"codec_name" : ".." , "width": ".." , "height": ".."}]}
# jsonb_array_elemnts is used to convert the array to a set which can
# be queried using a SELECT
#
# Beware: Super duper hack!
#
# TODO/FIXME: There is some way to construct these queries using the
# sqlalchemy query builder
# There just seems no good documentation (besides this -
# https://bitbucket.org/zzzeek/sqlalchemy/issues/3566/figure-out-how-to-support-all-of-pgs#comment-22842678)


def filter_multiple_codecs_and(codecs, i=0):
    parameters = []
    queries = []
    for codec in codecs:
        param_name = "codec_name_" + str(i)
        i = i + 1

        # No, there is no obvious SQL injection possible here
        # The format is just to include a parameter for sqlalchemy with
        # variable name
        # ...
        queries.append("""\
            (SELECT COUNT(1)
                FROM jsonb_array_elements(mediainfo -> 'streams') AS stream
                WHERE  stream ->> 'codec_name' = :{}
            ) > 0
        """.format(param_name))

        # ...
        # The user supplied parameters are bind to the query here
        # and inserted by sqlalchemy later
        parameters.append(bindparam(param_name, codec))

    return (" AND ".join(queries), parameters)


# Takes a lists of lists, applies filter_multiple_codecs_and
# on each lists and joins the output of each list with an OR
# example [["h264", "aac"], ["vp8"]] ==> (*codec_is* h264 AND *codec_is* aac)
# OR (*codec_is* vp8)
def filter_multiple_codecs_or(codecs):
    # filter_multiple_codecs_and doesn't return the sqlalchemy.text(string,
    #                                                               parameters)
    # version but the string and parameters seperately so they can be joined
    # by OR's here easily
    # thats why filter_multiple_codecs_and needs an optional argument,
    # the index from where to start naming parameters from to prevent
    # collisions
    i = 0
    and_queries = []

    # the text function from sqlalchemy expects bindparams to be
    # a list of objects returned by the bindparam function
    # filter_multiple_codecs_and returns such a list so we just need to join
    # the lists here
    parameters = []
    for and_codecs in codecs:
        (query, params) = filter_multiple_codecs_and(and_codecs, i=i)
        and_queries.append("(" + query + ")")
        parameters.extend(params)

        # filter_multiple_codecs_and used len(params) parameters
        i = i + len(params)

    return text(" OR ".join(and_queries), bindparams=parameters)


filter_width_greater_equals = """\
    (SELECT COUNT(1)
        FROM jsonb_array_elements(mediainfo -> 'streams') AS stream
        WHERE  (stream ->> 'width') >= ':width'
    ) > 0
 """


filter_height_greater_equals = """\
    (SELECT COUNT(1)
        FROM jsonb_array_elements(mediainfo -> 'streams') AS stream
        WHERE  (stream ->> 'height') >= ':height'
    ) > 0
"""


class Category(db.Model):
    __tablename__ = "category"
    category_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True, nullable=False)
    media = relationship("Media", back_populates="category")


class File(db.Model):
    __tablename__ = "files"
    file_hash = db.Column(db.VARCHAR,
                          ForeignKey("media.file_hash"),
                          nullable=False)
    path = db.Column(db.Text, nullable=False, unique=True, primary_key=True)


class MediaTag(db.Model):
    """
    Media - Tag Association class.
    Documentation: http://docs.sqlalchemy.org/en/latest/orm/basic_relationships.html#association-pattern
    """
    file_hash = Column(db.VARCHAR, db.ForeignKey("media.file_hash"), primary_key=True)
    tag_name = Column(db.Text, db.ForeignKey("tags.name"), primary_key=True)
    score = Column('score', db.Integer, default=0, nullable=False)
    medium = relationship("Media", back_populates="tags")
    tag = relationship("Tag", back_populates="media")


class Tag(db.Model):
    __tablename__ = "tags"
    name = db.Column(db.Text, primary_key=True)
    media = relationship("MediaTag", back_populates="tag")


class Media(db.Model):
    __tablename__ = "media"
    name = db.Column(db.Text, nullable=False)
    file_hash = db.Column(db.VARCHAR, primary_key=True)
    mediainfo = db.Column(postgresql.JSONB, nullable=False)
    lastModified = db.Column(db.DateTime, nullable=False)
    mimetype = db.Column(db.Text, nullable=False)
    files = db.relationship('File', backref='files', lazy='joined')
    category_id = Column(db.Integer,
                         ForeignKey("category.category_id"),
                         nullable=False)
    category = relationship("Category")
    tags = relationship("MediaTag", back_populates="medium")

    def api_fields(self, include_raw_mediainfo=False):

        mediainfo_for_api = {
            "file_hash": self.file_hash,
            "paths": [f.path for f in self.files],
            "tags": [(t.tag_name, t.score) for t in self.tags],
            "name": self.name,
            "category": self.category.name,
            "mimetype": self.mimetype,
            "last_modified": self.lastModified.ctime(),
            "raw_mediainfo": json.loads(self.mediainfo),
            "thumbnail": "",
        }

        return mediainfo_for_api


def get_or_create_category(name):
    r = Category.query.filter_by(name=name).first()
    if not r:
        r = Category(name=name)
        db.session.add(r)
        db.session.commit()
    return r


def get_or_create_tag(name):
    r = Tag.query.filter_by(name=name).first()
    if not r:
        r = Tag(name=name)
        db.session.add(r)
        db.session.commit()
    return r


# both codecs and mime are lists of lists
# the outer list means OR and the inner list means AND
def search_media(query=None, codecs=[],
                 width=None, height=None, category=None, mime=[],
                 tags=None, order_by=Media.lastModified.asc(), file_hash=None,
                 offset=0, limit=20):


    # combined_search_vector = Media.search_vector | Tag.search_vector | File.search_vector

    media = Media.query
    # media = Media.query.search(query, 'first')
    # media = (
    #     Media.query
    #     .join(tag_media_association_table)
    #     .join(Tag)
    #     .join(File)
    #     .filter(
    #         combined_search_vector.match(
    #             query
    #         )
    #     )
    # )

    if width:
        media = media.filter(text(filter_width_greater_equals,
                                  bindparams=[bindparam("width", width)]))

    if height:
        media = media.filter(text(filter_height_greater_equals,
                                  bindparams=[bindparam("height", height)]))

    if category:
        media = media.filter(Media.category_id == category)

    if file_hash:
        media = media.filter(Media.file_hash == file_hash)

    if tags:
        for tag in tags:
            media = media.filter(Media.tags.any(tag_id=tag))

    if len(mime) > 0:
        f = Media.mimetype == mime[0]

        if len(mime) > 1:
            for m in mime[1:]:
                f = f | (Media.mimetype == m)

        media = media.filter(f)

    media = media.order_by(order_by)

    count = media.count()

    return (count, media.limit(limit).offset(offset).all())
