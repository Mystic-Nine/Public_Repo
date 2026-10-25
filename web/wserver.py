#!/usr/bin/env python3
# Tiny health-check server.
# Heroku / Render / Railway need a process listening on $PORT, otherwise the service is
# marked as crashed. Nothing else is served from here.
from flask import Flask

app = Flask(__name__)


@app.route('/')
def homepage():
    return '<h1>Bot is running.</h1>'


@app.route('/health')
def health():
    return 'ok', 200


@app.errorhandler(404)
def page_not_found(e):
    return '<h1>404</h1>', 404
