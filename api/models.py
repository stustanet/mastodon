from api import db
from sqlalchemy.dialects import postgresql
from sqlalchemy import ForeignKey, Column, text, func
from sqlalchemy.orm import relationship, aliased
from sqlalchemy.sql.expression import bindparam
import urllib
from config import URL_TO_MOUNT, THUMBNAIL_ROOT_URL
import binascii
import videoinfo
import logging
from flask import jsonify, url_for

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
#
# Beware: Super duper hack!
#
# TODO/FIXME: There is some way to construct these queries using the sqlalchemy query builder
# There just seems no good documentation (besides this - https://bitbucket.org/zzzeek/sqlalchemy/issues/3566/figure-out-how-to-support-all-of-pgs#comment-22842678)
def filter_multiple_codecs_and(codecs, i=0):
    parameters = []
    queries = []
    for codec in codecs:
        param_name = "codec_name_" + str(i)
        i = i + 1

        # No, there is no obvious SQL injection possible here
        # The format is just to include a parameter for sqlalchemy with variable name
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
# example [["h264", "aac"], ["vp8"]] ==> (*codec_is* h264 AND *codec_is* aac) OR (*codec_is* vp8)
def filter_multiple_codecs_or(codecs):
    # filter_multiple_codecs_and doesn't return the sqlalchemy.text(string, parameters)
    # version but the string and parameters seperately so they can be joined by OR's here easily
    # thats why filter_multiple_codecs_and needs an optional argument,
    # the index from where to start naming parameters from to prevent collisions
    i = 0
    and_queries = []

    # the text function from sqlalchemy expects bindparams to be
    # a list of objects returned by the bindparam function
    # filter_multiple_codecs_and returns such a list so we just need to join the lists here
    parameters = []
    for and_codecs in codecs:
        (query, params) = filter_multiple_codecs_and(and_codecs, i=i)
        and_queries.append("(" + query + ")")
        parameters.extend(params)

        # filter_multiple_codecs_and used len(params) parameters
        i = i + len(params)


    return text(" OR ".join(and_queries), bindparams=parameters)

# This joins the fields <fields> in the metadata->data JSON object and splits the words
# This data can then be queried like usual by just doing a Query(split_metadata_words) or select_from()
def split_metadata_words(fields=["artist", "album", "title"]):
    s = []

    if len(fields) > 1:
        for field in fields[1:]:
            s.append(func.coalesce(func.jsonb_extract_path_text(Media.meta, "data", field)))

    return func.regexp_split_to_table(func.nullif(func.regexp_replace(func.concat(*s), "\s+", " "), " "), "\s").alias("words")

# media_search does two selects when including metadata into the result
# first only those with matching metadata (see query in search_metadata_from)
# then as usual all those with matching path. we need to exclude those with metadata
def filter_only_without_metadata(fields=["artist", "album", "title"]):
    # ?| operator: does the object contain any of these keys?
    s = "NOT meta ? 'data' OR NOT (meta -> 'data') ?| array["
    s = s + ",".join(["'{}'".format(field) for field in fields])
    s = s + "]"
    return text(s)


def filter_words_in(words):
    s = "words in ("
    ws = []

    i = 0
    for w in words:
        ws.append("':{}'".format(param_name))
        i = i + 1

    s = s + ")"



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
    lastModified = db.Column(db.Numeric(scale=6, asdecimal=False), nullable=False)
    mimetype = db.Column(db.Text, nullable=False)
    timeLastIndexed = db.Column(db.Numeric(scale=7, asdecimal=False), nullable=False)
    sha = db.Column(db.LargeBinary(length=32), nullable=False)

    # TODO/FIXME: One metadata for all files with same SHA
    meta = db.Column(postgresql.JSONB, nullable=False, default={})

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
        baseurl = urllib.parse.urljoin(URL_TO_MOUNT, urllib.parse.quote("/files/"))

        mediainfo_for_api = {
            "media_id": self.media_id,
            "path": self.path,
            "url": urllib.parse.urljoin(baseurl, urllib.parse.quote(self.path)),
            "duration": None,
            "streams": [],
            "category": self.category.name,
            "tags": tags,
            "mimetype": self.mimetype,
            "last_modified": self.lastModified,
            "last_indexed": self.timeLastIndexed,
            "sha": hex_sha,
            "raw_mediainfo" : None,
            "thumbnail": "",
            "metadata": self.meta

        }

        mediainfo_for_api["thumbnail"] = urllib.parse.urljoin(THUMBNAIL_ROOT_URL, hex_sha+".jpg")


        if "format" in self.mediainfo and "duration" in self.mediainfo["format"]:
            mediainfo_for_api["duration"] = \
              float(self.mediainfo["format"]["duration"])

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

def search_metadata_media(fields=["album", "title", "artist"]):
    s = []

    if len(fields) > 1:
        for field in fields[1:]:
            s.append(func.coalesce(func.jsonb_extract_path_text(Media.meta, "data", field)))

    t = func.regexp_split_to_table(func.nullif(func.regexp_replace(func.concat(*s), "\s+", " "), " "), "\s").alias("word")

    return Media.query.select_from(t).group_by("media_id").add_column("count(word) as score").all()

# both codecs and mime are lists of lists
# the outer list means OR and the inner list means AND
def search_media(query=None, codecs=[], search_meta=False, metadata_fields=["album", "artist", "title"],
                 width=None, height=None, category=None, mime=[],
                 tags=None, order_by="name_asc", sha=None, offset=0, limit=20):

    metadata_words = split_metadata_words(metadata_fields)

    # This needs an explanation:
    # This query consists of two subqueries which then get joined by UNION: one to fetch all media with matching metadata and one to fetch all
    # media which don't have metadata at all but with matching path
    # Those who have metadata receive a score which is just the number of words in all metadata fields matching the query words
    # We want the result to be
    # - Media with metadata first, ORDERED BY score DESC (to have the best matching media first)
    # - All media without metadata
    #   The user can decide how to sort this second *block* of results (path asc/desc, timeLastIndexed asc/desc)
    #   The results with metadata should always appear on top
    # We can achieve this by giving all the media wihtout metadata a score of 0 and then sort by score DESC
    # In order to let the user sort the second block of results we need a second ORDER BY
    # To make sure that the media with metadata always appear on top we sort by a custom column ord which for the media
    # without metadata is just the timeLastIndexed or path column, depending on the setting
    # for the media with metadata this ord column it is set to a constant which (should) have the effect of those results appear on top
    # path ASC -> "a"
    # path DESC -> "z"
    # time ASC -> -INFINITY
    # tie DESC -> INFINITY
    meta_ord = None
    non_meta_ord = None
    ord_order = None

    normal_query_order = None

    if order_by == "name_asc":
        meta_ord = "'a'"
        non_meta_ord = '"path"'
        ord_order = "ASC"
        normal_query_order = Media.path.asc()
    elif order_by == "name_desc":
        meta_ord = "'z'"
        non_meta_ord = '"path"'
        ord_order = "DESC"
        normal_query_order = Media.path.desc()
    elif order_by == "indexed_asc":
        meta_ord = "'-Infinity'::float8"
        non_meta_ord = '"timeLastIndexed"'
        ord_order = "ASC"
        normal_query_order = Media.timeLastIndexed.asc()
    elif order_by == "indexed_desc":
        meta_ord = "'Infinity'::float8"
        non_meta_ord = '"timeLastIndexed"'
        ord_order = "DESC"
        normal_query_order = Media.timeLastIndexed.desc()

    path_filter = None
    if query:
        words = query.split()

        if len(words) > 0:
            path_filter = Media.path.ilike("%{}%".format(words[0]))

            if len(words) > 1:
                for word in words[1:]:
                    path_filter = path_filter & Media.path.ilike("%{}%".format(word))

    meta_q = Media.query.select_from(metadata_words)
    meta_q = meta_q.add_column("count(words) as score").add_column(meta_ord + " as ord")
    meta_q = meta_q.filter(filter_words_in(query.split())).group_by("media_id")

    non_meta_q = Media.query.add_column("0 as score").add_column(non_meta_ord + " as ord")
    non_meta_q = non_meta_q.filter(filter_only_without_metadata(metadata_words)).filter(path_filter)

    q = None
    if search_meta:
        # Just do a normal query
        q = Media.query
        # we have to apply path filter here because it doesn't apply to meta_q
        # everything else does
        q.order_by(normal_query_order).filter(path_filter)

    else:
        q = meta_q.union(non_meta_q)

    if query:
        words = query.split()

        if len(words) > 0:
            path_query = Media.path.ilike("%{}%".format(words[0]))

            if len(words) > 1:
                for word in words[1:]:
                    path_query = path_query & Media.path.ilike("%{}%".format(word))

            q = q.filter(path_query)

    q = q.filter(filter_multiple_codecs_or(codecs))

    if width:
        q = q.filter(text(filter_width_greater_equals,
                                  bindparams=[bindparam("width", width)]))

    if height:
        q = q.filter(text(filter_height_greater_equals,
                                  bindparams=[bindparam("height", height)]))

    if category:
        q = q.filter(Media.category_id == category)

    if sha:
        q = q.filter(Media.sha == sha)

    if tags:
        for tag in tags:
            q = q.filter(Media.tags.any(tag_id=tag))

    if len(mime) > 0:
        f = Media.mimetype == mime[0]

        if len(mime) > 1:
            for m in mime[1:]:
                f = f | (Media.mimetype == m)

        q = q.filter(f)


    count = q.count()

    return (count, q.limit(limit).offset(offset).all())


