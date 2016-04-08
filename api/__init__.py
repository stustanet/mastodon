from flask import Flask
from flask_restful import reqparse, abort, Api, Resource
from flask.ext.sqlalchemy import SQLAlchemy
import config

app = Flask(__name__)
app.config.from_object("config")
db = SQLAlchemy(app)

from api import api
from api import models
