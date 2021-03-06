from flask import Blueprint, jsonify, render_template, Response, request
from flask_restful import reqparse
from .models import Media, Category, search_media, Tag, get_or_create_tag
from api import app
from config import basedir
from api import db
import os
import binascii

v1 = Blueprint('v1', __name__)


category_parser = reqparse.RequestParser()
# The codecs and mime argument can appear multiple times in a query
# Multiple occurences of these arguments mean an OR in the query
# example: ?codecs=h264,aac&codecs=vp8 means "(h264 AND aac) OR VP8"
category_parser.add_argument("codecs", required=False, default=[], action="append")
category_parser.add_argument("width", required=False, type=int)
category_parser.add_argument("height", required=False, type=int)
category_parser.add_argument("tag", required=False, action="append", default=[])
category_parser.add_argument("order_by", required=False, default="name_asc")
category_parser.add_argument("sha")
category_parser.add_argument("mime", action="append", default=[])
category_parser.add_argument("offset", default=0, type=int)
category_parser.add_argument("limit", default=20, type=int)

search_parser = category_parser.copy()
search_parser.add_argument("q")
search_parser.add_argument("category")


def do_search(args):
    """\
    Takes the output of search_parser as an argument and returns the output of the search_media function (an array)
    Returns a string with the error message for bad input
    Works with the output of category_parser as well
    """

    tags = []
    if "tag" in args:
        for tagname in args["tag"]:
            tag = Tag.query.filter_by(name=tagname).first()
            if tag:
                tags.append(tag.tag_id)
            else:
                return jsonify(media=[])

    order_by = None
    if args["order_by"] == "name_asc":
        order_by = Media.path.asc()
    elif args["order_by"] == "name_desc":
        order_by = Media.path.desc()
    elif args["order_by"] == "indexed_asc":
        order_by = Media.timeLastIndexed.asc()
    elif args["order_by"] == "indexed_desc":
        order_by = Media.timeLastIndexed.desc()

    sha = None
    if args["sha"]:
        if len(args["sha"]) != 64:
            return "sha too long"

        sha = binascii.unhexlify(args["sha"])

    limit = args["limit"]
    if limit > 100:
        limit = 100
    elif limit < 0:
        return "negative limit"

    if args["offset"] < 0:
        return "negative offset"

    if args["width"] != None and args["width"] < 0:
        return "negative width"

    if args["height"] != None and args["height"] < 0:
        return "negative height"

    codecs = []
    for codec in args["codecs"]:
        codecs.append(codec.split(","))

    return search_media(query=args["q"], codecs=codecs, mime=args["mime"],
        width=args["width"], height=args["height"], category=args["category"],
        tags=tags, order_by=order_by, sha=sha, limit=limit, offset=args["offset"])



@v1.route('/', methods=["GET"])
def doc():
    with open(os.path.join(basedir, "api/static/docs.txt"), "r") as f:
        return Response(f.read(), content_type='text')


@v1.route('/search', methods=["GET"])
def search():
    args = search_parser.parse_args()

    if args["category"]:
        category = Category.query.filter_by(name=args["category"]).first_or_404()
        args["category"] = category.category_id

    result = do_search(args)
    if type(result) is str:
        return "Bad Request: " + result, 400

    (count, media) = result

    return jsonify(total=count, media=[medium.api_fields() for medium in media])


@v1.route('/media/<int:media_id>', methods=["GET"])
def mediaById(media_id):
    medium = Media.query.filter_by(media_id=media_id).first_or_404()
    json = jsonify(**medium.api_fields(include_raw_mediainfo=True))
    return json


@v1.route("/media/<int:media_id>/tag/<tag_name>", methods=["POST", "DELETE"])
def mediaTag(media_id, tag_name):
    medium = Media.query.filter_by(media_id=media_id).first_or_404()
    tag = get_or_create_tag(tag_name)

    if request.method == "POST":
        medium.tags.append(tag)
    elif request.method == "DELETE":
        if tag in medium.tags:
            medium.tags.remove(tag)

    db.session.add(medium)
    db.session.commit()

    return jsonify(**medium.api_fields())


@v1.route('/category', methods=["GET"])
def category():
    categories = Category.query.all()

    json = jsonify(categories=[category.name
                               for category in categories])

    return json


@v1.route('/category/<category>', methods=["GET"])
def categoryById(category):
    args = category_parser.parse_args()
    args["q"] = None

    category = Category.query.filter_by(name=category).first_or_404()
    args["category"] = category.category_id

    result = do_search(args)
    if type(result) is str:
        return "Bad Request: " + result, 400

    (count, media) = result

    json = jsonify(total=count, media=[medium.api_fields() for medium in media])
    return json


@v1.route("/tag", methods=["GET"])
def tags():
    return jsonify(tags=[tag.name for tag in Tag.query.all()])
