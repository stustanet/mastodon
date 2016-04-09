from api import db
from sqlalchemy.dialects import postgresql
from sqlalchemy import ForeignKey, Column
from sqlalchemy.orm import relationship
import urllib
from config import THUMBNAIL_ROOT_URL, URL_TO_MOUNT
import binascii
import videoinfo

tag_media_association_table = db.Table('tag_media', db.metadata,
                                       Column('tag_id',
                                              db.Integer,
                                              db.ForeignKey('tag.id')),
                                       Column('media_id',
                                              db.Integer,
                                              db.ForeignKey('media.id')))


class Category(db.Model):
    __tablename__ = "category"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True, nullable=False)
    media = relationship("Media", back_populates="category")

    def api_fields(self):
        return {
            "id": self.id,
            "name": self.name
        }


class Tag(db.Model):
    __tablename__ = "tag"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True, nullable=False)

    media = relationship("Media",
                         secondary=tag_media_association_table,
                         back_populates="tags")


class Media(db.Model):
    __tablename__ = "media"

    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.Text, nullable=False, unique=True)
    mediainfo = db.Column(postgresql.JSON, nullable=False)
    lastModified = db.Column(db.Integer, nullable=False) # Last modified from filesystem (unix epoch)
    mimetype = db.Column(db.Text, nullable=False)
    timeLastIndexed = db.Column(db.Integer, nullable=False)
    sha = db.Column(db.Binary(length=32), nullable=False)

    # media requires a category
    category_id = Column(db.Integer, ForeignKey("category.id"), nullable=False)
    category = relationship("Category", back_populates="media")

    tags = relationship("Tag",
                        secondary=tag_media_association_table,
                        back_populates="media")

    def api_fields(self):
        hex_sha = self.sha.hex()
        tags = [tag.name for tag in self.tags]

        mediainfo_for_api = {
            "path": self.path,
            "url": urllib.parse.urljoin(URL_TO_MOUNT, self.path),
            "duration": None,
            "streams": [],
            "category_id": self.category_id,
            "tags": tags,
            "mimetype": self.mimetype,
            "last_modified": self.lastModified,
            "last_indexed": self.timeLastIndexed,
            "sha": hex_sha
        }

        if "format" in self.mediainfo:
          mediainfo_for_api["duration"] = float(self.mediainfo["format"]["duration"])

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

        return mediainfo_for_api

def get_or_create_category(name):
    r = Category.query.filter_by(name=name).first()
    if not r:
        r = Category(name=name)
        db.session.add(r)
        db.session.commit()
    return r
