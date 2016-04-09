from flask import Blueprint, jsonify
from flask_restful import reqparse
from .models import Media

v1 = Blueprint('v1', __name__)


search_parser = reqparse.RequestParser()
search_parser.add_argument('q',
                           required=True,
                           help="Query String cannot be blank!")
search_parser.add_argument('tags', action='append')


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


@v1.route('/media/<id>')
def mediabyid(id):
    args = search_parser.parse_args()
    response = jsonify(querystring=args['q'])
    return response
