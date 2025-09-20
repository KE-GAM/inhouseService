
import sqlite3, os
from flask import current_app, g

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')
DB_PATH = os.path.join(os.path.dirname(__file__), 'inhouse.sqlite3')

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        db.executescript(f.read())
    db.commit()
    db.close()

def init_db_command():
    init_db()
