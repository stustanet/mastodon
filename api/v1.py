from flask import Blueprint, jsonify
from flask_restful import reqparse
from .models import Media, Category

v1 = Blueprint('v1', __name__)


search_parser = reqparse.RequestParser()
search_parser.add_argument('q', required=True, help="Query String cannot be blank!")
search_parser.add_argument("vcodec", required=False)
search_parser.add_argument("acodec", required=False)
search_parser.add_argument("width", required=False)
search_parser.add_argument("height", required=False)
search_parser.add_argument("category", required=False)
search_parser.add_argument("tag", required=False, action="append", default=[])
search_parser.add_argument("sort_by", required=False, default="name_asc")


@v1.route('/')
def doc():
    return "DOCS"


@v1.route('/search')
def search():
    args = search_parser.parse_args()
    response = jsonify(querystring=args['q'])
    return response


@v1.route('/media/<int:id>')
def mediaById(id):
    medium = Media.query.filter_by(id=id).first_or_404()
    json = jsonify(**medium.api_fields())
    return json


@v1.route('/category')
def category():
    categories = Category.query.all()
    json = jsonify(categories=[category.api_fields() for category in categories])
    return json


@v1.route('/category/<int:id>')
def categoryById(id):
    media = Media.query.filter_by(category_id=id ).all()
    json = jsonify(media=[medium.api_fields() for medium in media])
    return json
