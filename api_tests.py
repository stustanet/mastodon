#!venv/bin/python
import unittest
from flask.ext.testing import TestCase
from api.models import Tag, Category, Media, get_or_create_category, get_or_create_tag, search_media
from api import app, db
import time
import mimetypes
import tempfile
import scraper
import os


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
        media = Media(path="/foo/bar",
                      mediainfo={"width": 100,
                                 "height": 100,
                                 "acodec": "aac",
                                 "vcodec": "h.265"},
                      category=get_or_create_category("test"),
                      mimetype="video",
                      lastModified=time.time(),
                      timeLastIndexed=time.time(),
                      sha=b'\x00'*32)

        db.session.add(media)
        db.session.commit()

        medias = Media.query.all()

        assert media in medias

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
                      lastModified=time.time(),
                      timeLastIndexed=time.time(),
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
                lastModified=time.time(),
                timeLastIndexed=time.time(),
                sha=b'\x00'*32,
                tags=[]),
            Media(path="/foo/Breaking.Bad.1",
                mediainfo={"streams": [
                    {"width": 300, "height": 300, "codec_type": "video", "codec_name": "h.265", "index":0, "duration": "30.0"},
                    {"width": None, "height": None, "codec_type": "audio", "codec_name": "aac", "index":1, "duration": "30.0"},
                ]},
                category=category1,
                mimetype="video/mp4",
                lastModified=time.time(),
                timeLastIndexed=time.time(),
                sha=b'\x00'*32,
                tags=[tag2]),
            Media(path="/foo/Breaking.Bad.2",
                mediainfo={"streams": [
                    {"width": 100, "height": 100, "codec_type": "video", "codec_name": "h.265", "index":0, "duration": "30.0"},
                    {"width": None, "height": None, "codec_type": "audio", "codec_name": "mp3", "index":1, "duration": "30.0"},
                ]},
                category=category1,
                mimetype="video/mp4",
                lastModified=time.time(),
                timeLastIndexed=time.time(),
                sha=b'\x00'*32,
                tags=[tag2]),
            Media(path="/Breaking Bad/Episode 1",
                mediainfo={"streams": [
                    {"width": None, "height": None, "codec_type": "audio", "codec_name": "h.264", "index":0, "duration": "30.0"},
                ]},
                category=category2,
                mimetype="audio/mp4",
                lastModified=time.time(),
                timeLastIndexed=time.time(),
                sha=b'\x00'*32,
                tags=[tag2, tag3])
        ]

        for media in medias:
            db.session.add(media)
        db.session.commit()

        # Check that basic querying + ordering works
        assert search_media(query="Breaking Bad")[1] == [medias[3], medias[1], medias[2]]
        assert search_media(query="Breaking Bad", order_by="name_desc") == [medias[2], medias[1], medias[3]]

        # Check that searching by category works
        assert search_media(query="Breaking Bad", category=category1.category_id)[1] == [medias[1], medias[2]]

        # Check that searching by tag works
        assert search_media(query="Breaking Bad", tags=[tag2.tag_id])[1] == [medias[3], medias[1], medias[2]]
        assert search_media(query="Breaking Bad", tags=[tag2.tag_id, tag3.tag_id])[1] == [medias[3]]

        # Check that searching by category and tag works
        assert search_media(query="Breaking Bad", tags=[tag2.tag_id, tag3.tag_id], category=category1.category_id)[1] == []

        # Check that searching by size works
        assert search_media(query="Breaking Bad", height=300, width=300)[1] == [medias[1]]

        # Check that searching by codec works
        assert search_media(query="Breaking Bad", codecs=[["h.264"]])[1] == [medias[3]]
        assert search_media(query="Breaking Bad", codecs=[["h.264"], ["h.265", "mp3"]])[1] == [medias[3], medias[2]]

        # Check that searchy by mime works
        assert search_media(query="Breaking Bad", mime=["audio/mp4"])[1] == [medias[3]]
        assert search_media(query="Breaking Bad", mime=["audio/mp4", "video/mp4"])[1] == [medias[3], medias[1], medias[2]]




class ScraperTestCase(TestCase):
    def create_app(self):
        app.config.from_object("config_test")
        return app

    def setUp(self):
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_get_deltas(self):
        temp_dir = tempfile.TemporaryDirectory()

        def write_file(name, content):
            with open(os.path.join(temp_dir.name, name), "w") as f:
                f.write(content)

        def get_info(name):
            path = os.path.join(temp_dir.name, name)

            return {
                "path": name,
                "lastModified": os.path.getmtime(path),
                "mime": mimetypes.guess_type(name)[0],
                "sha": scraper.hashfile(path),
                "fullpath": path
            }

        def delete_file(name):
            i = get_info(name)
            os.remove(os.path.join(temp_dir.name, name))
            return i

        def move_file(name, new_name):
            os.rename(os.path.join(temp_dir.name, name), os.path.join(temp_dir.name, new_name))


        write_file("file1.mp4", "test1")
        assert scraper.get_deltas([], scraper.get_files(temp_dir.name, temp_dir.name)) == ([get_info("file1.mp4")], [], [], [])

        db = [get_info("file1.mp4")]
        write_file("file2.mp4", "test2")
        write_file("file3.mp4", "test3")
        assert scraper.get_deltas(db, scraper.get_files(temp_dir.name, temp_dir.name)) == ([get_info("file3.mp4"), get_info("file2.mp4")], [], [], [])

        db = [get_info("file1.mp4"), get_info("file2.mp4"), get_info("file3.mp4")]
        assert scraper.get_deltas(db, scraper.get_files(temp_dir.name, temp_dir.name)) == ([], [], [], [])
        i = delete_file("file2.mp4")
        assert scraper.get_deltas(db, scraper.get_files(temp_dir.name, temp_dir.name)) == ([], [i], [], [])

        db = [get_info("file1.mp4"), get_info("file3.mp4")]
        assert scraper.get_deltas(db, scraper.get_files(temp_dir.name, temp_dir.name)) == ([], [], [], [])
        move_file("file3.mp4", "file2.mp4")
        i = get_info("file2.mp4")
        i["renamed_from"] = "file3.mp4"
        assert scraper.get_deltas(db, scraper.get_files(temp_dir.name, temp_dir.name)) == ([], [], [i], [])

        db = [get_info("file1.mp4"), get_info("file2.mp4")]
        assert scraper.get_deltas(db, scraper.get_files(temp_dir.name, temp_dir.name)) == ([], [], [], [])
        write_file("file2.mp4", "test2'")
        assert scraper.get_deltas(db, scraper.get_files(temp_dir.name, temp_dir.name)) == ([], [], [], [get_info("file2.mp4")])

        temp_dir.cleanup()

    def test_apply_deltas(self):
        temp_dir = tempfile.TemporaryDirectory()

        def write_file(name, content):
            with open(os.path.join(temp_dir.name, name), "w") as f:
                f.write(content)

        def delete_file(name):
            i = get_info(name)
            os.remove(os.path.join(temp_dir.name, name))
            return i

        def move_file(name, new_name):
            os.rename(os.path.join(temp_dir.name, name), os.path.join(temp_dir.name, new_name))

        def run():
            files = scraper.get_files(temp_dir.name, temp_dir.name)
            scraper.apply_deltas_to_db(scraper.get_deltas(scraper.get_files_in_db(), files))


        write_file("file1.mp4", "test1")
        write_file("file2.mp4", "test1")
        run()

        assert set([(m.path, m.category.name) for m in Media.query.all()]) == set([("file1.mp4", "uncategorized"), ("file2.mp4", "uncategorized")])

        m, m2 = Media.query.all()
        m.tags = [get_or_create_tag("tag1")]
        m.category = get_or_create_category("category1")

        assert len(Media.query.all()) == 2
        assert Media.query.filter_by(media_id=m.media_id).first().category.name == "category1"

        move_file(m.path, "Episode 1.mp4")
        run()

        m = Media.query.filter_by(media_id=m.media_id).first()
        assert m.path == "Episode 1.mp4"
        assert m.tags == [get_or_create_tag("tag1")]
        assert m.category.name == "Series"
        assert Media.query.filter_by(media_id=m2.media_id).first() == m2
        m.category = get_or_create_category("category1")

        write_file(m.path, "testtest")
        old_sha = m.sha
        run()

        assert len(Media.query.all()) == 2
        assert Media.query.filter_by(media_id=m2.media_id).first() == m2
        M = Media.query.filter_by(media_id=m.media_id).first()
        assert M.path == "Episode 1.mp4"
        assert M.tags == [get_or_create_tag("tag1")]
        assert M.sha != old_sha
        assert M.category.name == "category1"

        temp_dir.cleanup()

    def test_merge_metadata(self):
        # add data to empty DB column
        current = {}
        new = {"artist": "Foo"}
        assert scraper.merge_metadata(current, new) == {"entered_by_user": {"artist": False}, "data": new}

        current = scraper.merge_metadata({}, {"artist": "Foo"})
        new = {"artist": "Bar"}
        assert scraper.merge_metadata(current, new) == {"entered_by_user": {"artist": False}, "data": new}

        current = scraper.merge_metadata({}, {"artist": "Foo"})
        current["entered_by_user"]["artist"] = True
        current["data"]["artist"] = "FooBar"
        new = {"artist": "Bar"}
        assert scraper.merge_metadata(current, new) == {"entered_by_user": {"artist": True}, "data": {"artist": "FooBar"}}

        new = {"title": "Test"}
        merged =  {"entered_by_user": {"artist": True, "title": False}, "data": {"artist": "FooBar", "title": "Test"}}
        assert scraper.merge_metadata(current, new) == merged
        current = scraper.merge_metadata(current, new)

        new = {"nested": {"key": "val"}}
        merged =  {
            "entered_by_user": {"artist": True, "title": False, "nested": {"key": False}},
            "data": {"artist": "FooBar", "title": "Test", "nested": {"key": "val"}}
        }
        assert scraper.merge_metadata(current, new) == merged


if __name__ == '__main__':
    unittest.main()
