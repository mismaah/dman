import json
import sqlite3
from datetime import datetime
import helpers

con = sqlite3.connect("data.db")
cur = con.cursor()


def query(returnValues: bool, q, params=()):
    try:
        cur.execute(q, params)
        if returnValues:
            return cur.fetchall()
        else:
            con.commit()
    except sqlite3.OperationalError as e:
        if str(e).split(": ")[0] == "no such table":
            createTable(str(e).split(": ")[1])
            return query(returnValues, q, params)
        else:
            raise e


def fetch(q, params=()):
    return query(True, q, params)


def mutate(q, params=()):
    query(False, q, params)


def find(name):
    q = "SELECT id, name, path, created, current_revision_id FROM sources WHERE "
    (isInt, id) = helpers.isInt(name)
    if isInt:
        q = q + f"id = {id}"
    else:
        q = q + f"name LIKE '%{name}%'"
    source = fetch(q)
    if len(source) == 0:
        return None
    source = {
        "id": source[0][0],
        "name": source[0][1],
        "path": source[0][2],
        "created": source[0][3],
        "currentRevisionId": source[0][4],
    }
    revision = fetch(
        "SELECT id, sourceId, created, checksum, value FROM revisions WHERE id = ?",
        params=(source["currentRevisionId"],),
    )
    revision = {
        "id": revision[0][0],
        "sourceId": revision[0][1],
        "created": revision[0][2],
        "checksum": revision[0][3],
        "value": json.loads(revision[0][4]),
    }
    return (source, revision)


def createTable(name):
    print(name)
    query = ""
    if name == "sources":
        query = f"CREATE TABLE {name} (id INTEGER PRIMARY KEY, name TEXT UNIQUE, path TEXT, created INTEGER, current_revision_id TEXT)"
    elif name == "revisions":
        query = f"CREATE TABLE {name} (id TEXT PRIMARY KEY, sourceId INTEGER, created INTEGER, checksum TEXT, value TEXT)"
    elif name == "logs":
        query = f"CREATE TABLE {name} (id INTEGER PRIMARY KEY, timestamp INTEGER, commands TEXT)"
    elif name == "ignore":
        query = f"CREATE TABLE {name} (id INTEGER PRIMARY KEY, value TEXT UNIQUE)"
    else:
        return
    cur.execute(query)
    con.commit()


def revCount(sourceId):
    count = fetch(f"SELECT count(*) FROM revisions WHERE sourceId = {sourceId}")
    count = count[0][0]
    return count - 1


def logSession(args):
    mutate(
        f"INSERT INTO logs (timestamp, commands) VALUES ({datetime.now().timestamp()}, '{' '.join(args)}');"
    )
