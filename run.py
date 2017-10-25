#!venv/bin/python
from api import app

def run():
    app.run(host='127.0.0.1', port=8080, debug=True)

if __name__ == '__main__':
    run()
