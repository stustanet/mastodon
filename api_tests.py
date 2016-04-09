#!venv/bin/python
import unittest
from flask.ext.testing import TestCase
from api.models import Tag, Category, Media
from api import app, db
import time
import scraper


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
          category=category,
          mimetype="video",
          lastModified=int(time.time()),
          timeLastIndexed=int(time.time()),
          sha=b'\x00'*32)

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
          category=category,
          mimetype="video",
          lastModified=int(time.time()),
          timeLastIndexed=int(time.time()),
          sha=b'\x00'*32)

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


class ScraperTestCase(TestCase):
    def create_app(self):
        app.config.from_object("config_test")
        return app

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_deltas(self):
        # handles new files correctly
        database_files = []
        filesystem_files = [("test_file.mp4", "video", 1)]
        (to_upsert, to_delete) = scraper.get_deltas(database_files, filesystem_files)
        assert to_upsert == filesystem_files
        assert to_delete ==  []

        # handles deleted files correctly
        database_files = [("test_file.mp4", "video", 1), ("test_file2.mp4", "video", 3)]
        filesystem_files = [("test_file2.mp4", "video", 3)]
        (to_upsert, to_delete) = scraper.get_deltas(database_files, filesystem_files)
        assert to_upsert == []
        assert to_delete ==  [("test_file.mp4", "video", 1)]

        # handles updates files correctly
        database_files = [("test_file.mp4", "video", 1), ("test_file2.mp4", "video", 3)]
        filesystem_files = [("test_file2.mp4", "video", 4)]
        (to_upsert, to_delete) = scraper.get_deltas(database_files, filesystem_files)
        assert to_upsert == [("test_file2.mp4", "video", 4)]
        assert to_delete ==  [("test_file.mp4", "video", 1), ("test_file2.mp4", "video", 3)]


if __name__ == '__main__':
    unittest.main()
