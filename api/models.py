from api import db
from sqlalchemy.dialects import postgresql
from sqlalchemy import ForeignKey, Column, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import bindparam
import urllib
from config import URL_TO_MOUNT
import binascii
import videoinfo
import logging
from flask import jsonify

tag_media_association_table = db.Table('tag_media',
                                       db.metadata,
                                       Column('tag_id',
                                              db.Integer,
                                              db.ForeignKey('tag.tag_id')),
                                       Column('media_id',
                                              db.Integer,
                                              db.ForeignKey('media.media_id', ondelete="cascade")))

# These queries search in the mediainfo JSON which looks like this
# {"streams" : [{"codec_name" : ".." , "width": ".." , "height": ".."}]}
# jsonb_array_elemnts is used to convert the array to a set which can
# be queried using a SELECT
# Beware: Super duper hack!
def filter_multiple_codecs(codecs):
    s = ""
    parameters = []
    i = 1
    for codec in codecs:
        param_name = "codec_name_" + str(i)

        if i > 1:
            s += " AND "

        s += """\
            (SELECT COUNT(1)
                FROM jsonb_array_elements(mediainfo -> 'streams') AS stream
                WHERE  stream ->> 'codec_name' = :{}
            ) > 0
        """.format(param_name)

        parameters.append(bindparam(param_name, codec))

        i += 1

    return text(s, bindparams=parameters)


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

    def api_fields(self):
        return {
            "category_id": self.category_id,
            "name": self.name
        }


class Tag(db.Model):
    __tablename__ = "tag"

    tag_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True, nullable=False)

    media = relationship("Media",
                         secondary=tag_media_association_table,
                         back_populates="tags")


class Media(db.Model):
    __tablename__ = "media"

    media_id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.Text, nullable=False, unique=True)
    mediainfo = db.Column(postgresql.JSONB, nullable=False)
    lastModified = db.Column(db.Integer,
                             # Last modified from filesystem (unix epoch)
                             nullable=False)
    mimetype = db.Column(db.Text, nullable=False)
    timeLastIndexed = db.Column(db.Integer, nullable=False)
    sha = db.Column(db.Binary(length=32), nullable=False)

    # media requires a category
    category_id = Column(db.Integer,
                         ForeignKey("category.category_id"),
                         nullable=False)
    category = relationship("Category", back_populates="media")

    tags = relationship("Tag",
                        secondary=tag_media_association_table,
                        back_populates="media",
                        cascade="all")

    def api_fields(self, include_raw_mediainfo=False):
        hex_sha = binascii.hexlify(self.sha).decode("ascii")
        tags = [tag.name for tag in self.tags]

        mediainfo_for_api = {
            "media_id": self.media_id,
            "path": self.path,
            "url": urllib.parse.urljoin(URL_TO_MOUNT,
                                        urllib.parse.quote(self.path)),
            "duration": None,
            "streams": [],
            "category_id": self.category_id,
            "tags": tags,
            "mimetype": self.mimetype,
            "last_modified": self.lastModified,
            "last_indexed": self.timeLastIndexed,
            "sha": hex_sha,
            "raw_mediainfo" : None
        }

        if "format" in self.mediainfo:
            mediainfo_for_api["duration"] = \
              float(self.mediainfo["format"]["duration"])

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

            if not s["duration"]:
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


def search_media(query=None, codecs=[],
                 width=None, height=None, category=None, mime=None,
                 tags=None, order_by=Media.path.asc(), sha=None, offset=0, limit=20):
    media = Media.query

    if query:
        for word in query.split():
            media = media.filter(Media.path.ilike("%{}%".format(word)))

    media = media.filter(filter_multiple_codecs(codecs))

    if width:
        media = media.filter(text(filter_width_greater_equals,
                                  bindparams=[bindparam("width", width)]))

    if height:
        media = media.filter(text(filter_height_greater_equals,
                                  bindparams=[bindparam("height", height)]))

    if category:
        media = media.filter(Media.category ==
                             Category.query.filter_by
                             (category_id=category).first())

    if sha:
        media = media.filter(Media.sha == sha)

    if tags:
        for tag in tags:
            media = media.filter(Media.tags.any(tag_id=tag))

    if mime:
        media = media.filter(Media.mimetype == mime)

    media = media.order_by(order_by)

    return media.limit(limit).offset(offset).all()
