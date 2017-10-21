Mastodon
=========================================================

Mastodon is a generic media file indexer. It provides a RESTful API to query and filter indexed files and their meta data.

How do I run this?
-----------------

* Create a virtual environment named venv, using `virtualenv -p /usr/bin/python3 venv`

* Next install flask and necessary extensions with:

`pip install -r requirements.txt` 

* Fill in your configuration details in config.py (copy it from [config_template.py](config_template.py))

* The testserver can be run with `./run.py`

* See API docs here: `[host]:[port]/api/v1/`
