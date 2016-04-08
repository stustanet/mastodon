import unittest
from flask.ext.testing import TestCase
import config_test
from api.models import Tag, Category, Media
from api import app, db

class ModelTestCase(TestCase):

  def create_app(self):
    app.config.from_object("config_test")
    return app

  def setUp(self):
    db.create_all()

  def tearDown(self):
    db.session.remove()
    db.drop_all()

  def test_media(self):
    category = Category(name="Test category")
    db.session.add(category)

    media = Media(path="/foo/bar",
      mediainfo={"width":100, "height":100, "acodec": "aac", "vcodec": "h.265"},
      category=category)

    db.session.add(media)
    db.session.commit()

    medias = Media.query.all()

    assert media in medias
    assert media in category.media

  def test_tags(self):
    category = Category(name="Test category")
    db.session.add(category)

    media = Media(path="/foo/bar",
      mediainfo={"width":100, "height":100, "acodec": "aac", "vcodec": "h.265"},
      category=category)

    db.session.add(media)
    db.session.commit()

    tag1 = Tag(name="tag1")
    tag2 = Tag(name="tag2")
    db.session.add(tag1)
    db.session.add(tag2)

    media.tags.append(tag1)
    media.tags.append(tag2)

    medias = Media.query.all()

    assert media in medias
    assert medias[0].tags == [tag1, tag2]






if __name__ == '__main__':
    unittest.main()
