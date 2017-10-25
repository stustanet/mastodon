from flask import Flask, url_for, redirect
import config
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

app = Flask(__name__)
# Cross origin resources
# Doc: https://github.com/corydolphin/flask-cors
CORS(app)
app.config.from_object("config")
db = SQLAlchemy(app)
db.create_all()

from api.v1 import v1

app.register_blueprint(v1, url_prefix='/api/v1')


@app.route('/api')
def index():
    """\
    Routes '/api' to current api versions '/'
    """
    return redirect(url_for('v1.doc'))

from api import models
