from flask import Flask, url_for, redirect
from flask.ext.sqlalchemy import SQLAlchemy
import config
from flask.ext.cors import CORS

app = Flask(__name__)
CORS(app)
app.config.from_object("config")
db = SQLAlchemy(app)

from api.v1 import v1

app.register_blueprint(v1, url_prefix='/api/v1')


@app.route('/api')
def index():
    """\
    Routes '/api' to current api versions '/'
    """
    return redirect(url_for('v1.doc'))

from api import models

