import json
import sqlite3
from datetime import datetime
import helpers

con = sqlite3.connect("data.db")
cur = con.cursor()


def query(q, params=()):
    try:
        cur.execute(q, params)
        return cur.fetchall()
    except sqlite3.OperationalError as e:
        if str(e).split(": ")[0] == "no such table":
            createTable(str(e).split(": ")[1])
            return query(q)
        else:
            raise e


def mutate(q, params=()):
    try:
        cur.execute(q, params)
        con.commit()
    except sqlite3.OperationalError as e:
        if str(e).split(": ")[0] == "no such table":
            createTable(str(e).split(": ")[1])
            mutate(q)
        else:
            raise e


def find(name):
    q = "SELECT id, value FROM sources WHERE "
    (isInt, id) = helpers.isInt(name)
    if isInt:
        q = q + f"id = {id}"
    else:
        q = q + f"name LIKE '%{name}%'"
    source = query(q)
    if len(source) == 0:
        return None
    source = (source[0][0], json.loads(source[0][1]))
    return source


def createTable(name):
    print(name)
    query = ""
    if name == "sources":
        query = f"CREATE TABLE {name} (id INTEGER PRIMARY KEY, name TEXT, value TEXT)"
    elif name == "revisions":
        query = f"CREATE TABLE {name} (id INTEGER PRIMARY KEY, sourceId INTEGER, value TEXT)"
    elif name == "logs":
        query = f"CREATE TABLE {name} (id INTEGER PRIMARY KEY, timestamp INTEGER, commands TEXT)"
    elif name == "ignore":
        query = f"CREATE TABLE {name} (id INTEGER PRIMARY KEY, value TEXT UNIQUE)"
    else:
        return
    cur.execute(query)
    con.commit()


def revCount(sourceId):
    count = query(f"SELECT count(*) FROM revisions WHERE sourceId = {sourceId}")
    count = count[0][0]
    return count


def logSession(args):
    mutate(
        f"INSERT INTO logs (timestamp, commands) VALUES ({datetime.now().timestamp()}, '{' '.join(args)}');"
    )
