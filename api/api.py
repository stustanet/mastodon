from flask_restful import reqparse, abort, Api, Resource
from api import app

api = Api(app)

Categories = {
    'movies': {'title': 'Movies'},
    'music': {'title': 'Music'}
}

Medias = {
    'media1': {'title': 'Test1',
               'info': 'blablabal'},
    'media2': {'title': 'Test2',
               'info': 'basdad'}
}


def abort_if_media_doesnt_exist(media_id):
    if media_id not in Medias:
        abort(404, message="Media {} doesn't exist".format(media_id))


def abort_if_category_doesnt_exist(category_id):
    if category_id not in Categories:
        abort(404, message="Category {} doesn't exist".format(category_id))


class Category(Resource):
    def get(self, category_id):
        abort_if_category_doesnt_exist(category_id)
        return Categories[category_id]


class CategoryList(Resource):
    def get(self):
        return Categories


class Media(Resource):
    def get(self, media_id):
        abort_if_media_doesnt_exist(media_id)
        return Medias[media_id]


class MediaList(Resource):
    def get(self):
        return Medias


class Search(Resource):
    def get(self):
        args = search_parser.parse_args()
        media_id = args['q']
        abort_if_media_doesnt_exist(media_id)
        return Medias[media_id]

api.add_resource(Media, '/api/v1/media/<media_id>')
api.add_resource(MediaList, '/api/v1/media')
api.add_resource(CategoryList, '/api/v1/category')
api.add_resource(Category, '/api/v1/category/<category_id>')
api.add_resource(Search, '/api/v1/search')


search_parser = reqparse.RequestParser()
search_parser.add_argument('q',
                           required=True,
                           help="Query String cannot be blank!")
search_parser.add_argument('tags', action='append')
