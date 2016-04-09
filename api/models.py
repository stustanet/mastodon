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
        hex_sha = binascii.hexlify(self.sha)
        tags = [tag.name for tag in self.tags]
        video_stream = videoinfo.get_video_stream_info()
        audio_stream = videoinfo.get

        mediainfo_for_api = {
            "path": self.path,
            "url": urllib.parse.urljoin(URL_TO_MOUNT, self.path),
            "width": None,
            "height": None,
            "duration": None,
            "vcodec": None,
            "acodec": None,
            "category_id": self.category_id,
            "tags": tags,
            "mimetype": self.mimetype,
            "thumbnail_url": urllib.parse.urljoin(THUMBNAIL_ROOT_URL, hex_sha),
            "last_modified": self.lastModified,
            "last_indexed": self.timeLastIndexed,
            "sha": hex_sha
        }

        if "format" in self.mediainfo:
          mediainfo_for_api["duration"] = float(self.mediainfo["format"]["duration"])

        if video_stream:
          mediainfo_for_api["width"] = video_stream["width"]
          mediainfo_for_api["height"] = video_stream["height"]
          mediainfo_for_api["vcodec"] = video_stream["codec_name"]

        if audio_stream:
          mediainfo_for_api["acodec"] = audio_stream["codec_name"]

        return mediainfo_for_api


def get_or_create_category(name):
    r = Category.query.filter_by(name=name).first()
    if not r:
        r = Category(name=name)
        db.session.add(r)
        db.session.commit()
    return r
