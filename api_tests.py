#!venv/bin/python
import unittest
from flask.ext.testing import TestCase
from api.models import Tag, Category, Media, get_or_create_category, get_or_create_tag, search_media
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
                      mediainfo={"width": 100,
                                 "height": 100,
                                 "acodec": "aac",
                                 "vcodec": "h.265"},
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
                      mediainfo={"width": 100,
                                 "height": 100,
                                 "acodec": "aac",
                                 "vcodec": "h.265"},
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

    def test_search(self):
        category1 = get_or_create_category("category1")
        category2 = get_or_create_category("category2")

        tag1 = get_or_create_tag("tag1")
        tag2 = get_or_create_tag("tag2")
        tag3 = get_or_create_tag("tag3")

        medias = [
            Media(path="/foo/Breaking",
                mediainfo={"streams": [
                    {"width": 300, "height": 300, "codec_type": "video", "codec_name": "h.264", "index":0, "duration": "30.0"},
                    {"width": None, "height": None, "codec_type": "audio", "codec_name": "aac", "index":1, "duration": "30.0"},
                ]},
                category=category1,
                mimetype="video/mp4",
                lastModified=int(time.time()),
                timeLastIndexed=int(time.time()),
                sha=b'\x00'*32,
                tags=[]),
            Media(path="/foo/Breaking.Bad.1",
                mediainfo={"streams": [
                    {"width": 300, "height": 300, "codec_type": "video", "codec_name": "h.265", "index":0, "duration": "30.0"},
                    {"width": None, "height": None, "codec_type": "audio", "codec_name": "mp3", "index":1, "duration": "30.0"},
                ]},
                category=category1,
                mimetype="video/mp4",
                lastModified=int(time.time()),
                timeLastIndexed=int(time.time()),
                sha=b'\x00'*32,
                tags=[tag2]),
            Media(path="/foo/Breaking.Bad.2",
                mediainfo={"streams": [
                    {"width": 100, "height": 100, "codec_type": "video", "codec_name": "h.265", "index":0, "duration": "30.0"},
                    {"width": None, "height": None, "codec_type": "audio", "codec_name": "mp3", "index":1, "duration": "30.0"},
                ]},
                category=category1,
                mimetype="video/mp4",
                lastModified=int(time.time()),
                timeLastIndexed=int(time.time()),
                sha=b'\x00'*32,
                tags=[tag2]),
            Media(path="/Breaking Bad/Episode 1",
                mediainfo={"streams": [
                    {"width": None, "height": None, "codec_type": "audio", "codec_name": "h.264", "index":0, "duration": "30.0"},
                ]},
                category=category2,
                mimetype="audio/mp4",
                lastModified=int(time.time()),
                timeLastIndexed=int(time.time()),
                sha=b'\x00'*32,
                tags=[tag2, tag3])
        ]

        for media in medias:
            db.session.add(media)
        db.session.commit()

        # Check that basic querying + ordering works
        assert search_media(query="Breaking Bad") == [medias[3], medias[1], medias[2]]
        assert search_media(query="Breaking Bad", order_by=Media.path.desc()) == [medias[2], medias[1], medias[3]]

        # Check that searching by category works
        assert search_media(query="Breaking Bad", category=category1.category_id) == [medias[1], medias[2]]

        # Check that searching by tag works
        assert search_media(query="Breaking Bad", tags=[tag2.tag_id]) == [medias[3], medias[1], medias[2]]
        assert search_media(query="Breaking Bad", tags=[tag2.tag_id, tag3.tag_id]) == [medias[3]]

        # Check that searching by category and tag works
        assert search_media(query="Breaking Bad", tags=[tag2.tag_id, tag3.tag_id], category=category1.category_id) == []

        # Check that searching by size works
        assert search_media(query="Breaking Bad", height=300, width=300) == [medias[1]]

        # Check that searching by codec works
        assert search_media(query="Breaking Bad", codecs=["h.264"]) == [medias[3]]




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
