from flask import Flask
from flask_restful import reqparse, abort, Api, Resource

app = Flask(__name__)
api = Api(app)

Categories = {
    'movies': {'title': 'Movies'},
    'music': {'title': 'Music'}
}

Videos = {
    'video1': {'title': 'Test1',
               'info': 'blablabal'},
    'video2': {'title': 'Test2',
               'info': 'basdad'}
}


def abort_if_video_doesnt_exist(video_id):
    if video_id not in Videos:
        abort(404, message="Video {} doesn't exist".format(video_id))


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


class Video(Resource):
    def get(self, video_id):
        abort_if_video_doesnt_exist(video_id)
        return Videos[video_id]


class Search(Resource):
    def get(self):
        args = search_parser.parse_args()
        video_id = args['q']
        abort_if_video_doesnt_exist(video_id)
        return Videos[video_id]

api.add_resource(Video, '/api/v1/video/<video_id>')
api.add_resource(CategoryList, '/api/v1/category')
api.add_resource(Category, '/api/v1/category/<category_id>')
api.add_resource(Search, '/api/v1/search')


search_parser = reqparse.RequestParser()
search_parser.add_argument('q',
                           required=True,
                           help="Query String cannot be blank!")
search_parser.add_argument('tags', action='append')


def run():
    app.run(host='0.0.0.0', port=8080, debug=True)

if __name__ == '__main__':
    app.run(debug=True)
