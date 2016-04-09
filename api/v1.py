from flask import Blueprint, jsonify, render_template, Response
from flask_restful import reqparse
from .models import Media, Category, search_media
from api import app
from config import basedir
import os

v1 = Blueprint('v1', __name__)


search_parser = reqparse.RequestParser()
search_parser.add_argument('q',
                           required=True,
                           help="Query String cannot be blank!")
search_parser.add_argument("vcodec", required=False)
search_parser.add_argument("acodec", required=False)
search_parser.add_argument("width", required=False, type=int)
search_parser.add_argument("height", required=False, type=int)
search_parser.add_argument("category", required=False, type=int)
search_parser.add_argument("tag", required=False, action="append", default=[])
search_parser.add_argument("order_by", required=False, default="name_asc")


@v1.route('/')
def doc():
    with open(os.path.join(basedir, "api/static/docs.txt"), "r") as f:
        return Response(f.read(), content_type='text')


@v1.route('/search')
def search():
    args = search_parser.parse_args()

    # Check that the category exists
    if "category" in args and args["category"]:
        if 0 == Category.query.filter_by(id=int(args["category"])).count():
            return "Bad Request", 400

    tags = []
    if "tag" in args:
        for tag_id in args["tag"]:
            if 0 < Tag.query.filter_by(tag_id=int(tag_id)).count():
                tags.append(tag)

    order_by = None
    if args["order_by"] == "name_asc":
        order_by = Media.path.asc()
    elif args["order_by"] == "name_desc":
        order_by = Media.path.desc()
    elif args["order_by"] == "indexed_asc":
        order_by = Media.timeLastIndexed.asc()
    elif args["order_by"] == "indexed_desc":
        order_by = Media.timeLastIndexed.desc()

    media = search_media(query=args["q"], vcodec=args["vcodec"],
        acodec=args["acodec"], width=args["width"], height=args["height"], category=args["category"],
        tags=tags, order_by=order_by)

    return jsonify(media=[medium.api_fields() for medium in media])


@v1.route('/media/<int:media_id>')
def mediaById(media_id):
    medium = Media.query.filter_by(media_id=media_id).first_or_404()
    json = jsonify(**medium.api_fields())
    return json


@v1.route('/category')
def category():
    categories = Category.query.all()
    json = jsonify(categories=[category.api_fields()
                               for category in categories])
    return json


@v1.route('/category/<int:category_id>')
def categoryById(category_id):
    media = Media.query.filter_by(category_id=category_id).all()
    json = jsonify(media=[medium.api_fields() for medium in media])
    return json
