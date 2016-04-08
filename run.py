#!flask/bin/python
from api import app

def run():
    app.run(host='0.0.0.0', port=8080, debug=True)

if __name__ == '__main__':
    app.run(debug=True)
