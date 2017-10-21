from api import db
from sqlalchemy.dialects import postgresql
from sqlalchemy import Foreignkey, Column, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import bindparam
import urllib
from config import URL_TO_MOUNT, THUMBNAIL_ROOT_URL
import binascii
import videoinfo
import logging
import os
from flask import jsonify, url_for


tag_media_association_table = db.Table('tag_media',
                                       db.metadata,
                                       Column('tag_id',
                                              db.Integer,
                                              db.ForeignKey('tag.tag_id')),
                                       Column('file_hash',
                                              db.Integer,
                                              db.ForeignKey('media.file_hash',
                                                            ondelete="cascade")))

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


class Tag(db.Model):
    __tablename__ = "tag"

    tag_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True, nullable=False)

    media = relationship("Media",
                         secondary=tag_media_association_table,
                         back_populates="tags")


class File(db.Model):
    __tablename__ = "files"

    file_hash = db.Column(db.LargeBinary(length=32),
                          ForeignKey("media.file_hash"),
                          nullable=False)
    path = db.Column(db.Text, nullable=False, unique=True, primary_key=True)


class Media(db.Model):
    __tablename__ = "media"

    file_hash = db.Column(db.LargeBinary(length=32), nullable=False, unique=True, primary_key=True)
    mediainfo = db.Column(postgresql.JSONB, nullable=False)
    lastModified = db.Column(db.Time, nullable=False)
    mimetype = db.Column(db.Text, nullable=False)

    # media requires a category
    category_id = Column(db.Integer,
                         ForeignKey("category.category_id"),
                         nullable=False)
    category = relationship("Category")

    tags = relationship("Tag",
                        secondary=tag_media_association_table,
                        back_populates="media",
                        cascade="all")

    def api_fields(self, include_raw_mediainfo=False):
        hex_sha = binascii.hexlify(self.sha).decode("ascii")
        tags = [tag.name for tag in self.tags]

        mediainfo_for_api = {
            "title": None,
            "file_hash": self.file_hash,
            "path": self.path,
            "url": urllib.parse.urljoin(URL_TO_MOUNT,
                                        urllib.parse.quote(self.path)),
            "duration": None,
            "streams": [],
            "category": self.category.name,
            "tags": tags,
            "mimetype": self.mimetype,
            "last_modified": self.lastModified,
            "sha": hex_sha,
            "raw_mediainfo": None,
            "thumbnail": "",
            "size": None
        }

        mediainfo_for_api["thumbnail"] = \
            urllib.parse.urljoin(THUMBNAIL_ROOT_URL, hex_sha+".jpg")


        if "format" in self.mediainfo and "duration" in self.mediainfo["format"]:
            mediainfo_for_api["duration"] = \
              float(self.mediainfo["format"]["duration"])

        if "format" in self.mediainfo and "size" in \
           self.mediainfo["format"]:
            mediainfo_for_api["size"] = \
              float(self.mediainfo["format"]["size"])

        if "format" in self.mediainfo and "tags" in \
           self.mediainfo["format"] and "title" in \
           self.mediainfo["format"]["tags"]:
            mediainfo_for_api["title"] = \
              self.mediainfo["format"]["tags"]["title"]
        else:
            mediainfo_for_api["title"] = \
              os.path.splitext(os.path.basename(os.path.normpath(self.path)))[0]

        if "streams" in self.mediainfo:
            for stream in self.mediainfo["streams"]:
                # TODO: add audio stream language
                s = {
                    "index": stream.get("index"),
                    "codec": stream.get("codec_name"),
                    "width": stream.get("width"),
                    "height": stream.get("height"),
                    "duration": stream.get("duration"),
                    "type": stream.get("codec_type")
                }

                if not s["duration"] and "duration" in mediainfo_for_api:
                    s["duration"] = mediainfo_for_api["duration"]

                mediainfo_for_api["streams"].append(s)

        if include_raw_mediainfo:
            mediainfo_for_api["raw_mediainfo"] = self.mediainfo

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
                 tags=None, order_by=Media.lastModified.asc(), sha=None,
                 offset=0, limit=20):
    media = Media.query

    if query:
        for word in query.split():
            media = media.filter(Media.tags.ilike("%{}%".format(word)))

    media = media.filter(filter_multiple_codecs_or(codecs))

    if width:
        media = media.filter(text(filter_width_greater_equals,
                                  bindparams=[bindparam("width", width)]))

    if height:
        media = media.filter(text(filter_height_greater_equals,
                                  bindparams=[bindparam("height", height)]))

    if category:
        media = media.filter(Media.category_id == category)

    if sha:
        media = media.filter(Media.sha == sha)

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
