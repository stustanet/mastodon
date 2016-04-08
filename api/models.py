from api import db
from sqlalchemy.dialects import postgresql
from sqlalchemy import ForeignKey, Table, Column
from sqlalchemy.orm import relationship

tag_media_association_table = db.Table('tag_media', db.metadata,
    Column('tag_id', db.Integer, db.ForeignKey('tag.id')),
    Column('media_id', db.Integer, db.ForeignKey('media.id'))
)



class Category(db.Model):
  __tablename__ = "category"

  id = db.Column(db.Integer, primary_key=True)
  name = db.Column(db.Text, unique=True, nullable=False)
  media = relationship("Media", back_populates="category")

class Tag(db.Model):
  __tablename__ = "tag"

  id = db.Column(db.Integer, primary_key=True)
  name = db.Column(db.Text, unique=True, nullable=False)

  media = relationship("Media", secondary=tag_media_association_table, back_populates="tags")

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

  tags = relationship("Tag", secondary=tag_media_association_table, back_populates="media")


def get_or_create_category(name):
    r = Category.query.filter_by(name=name).first()
    if not r:
        r = Category(name=name)
        db.session.add(r)
        db.session.commit()
    return r


