import os
import sys
import json
import copy
import sqlite3
from datetime import datetime
from helpers import *

con = sqlite3.connect("data.db")
cur = con.cursor()
verbose = False


def query(q):
    try:
        cur.execute(q)
        return cur.fetchall()
    except sqlite3.OperationalError as e:
        if str(e).split(": ")[0] == "no such table":
            createTable(str(e).split(": ")[1])
            return query(q)
        else:
            print(e)


def mutate(q):
    try:
        cur.execute(q)
        con.commit()
    except sqlite3.OperationalError as e:
        if str(e).split(": ")[0] == "no such table":
            createTable(str(e).split(": ")[1])
            mutate(q)
        else:
            print(e)


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


def guide():
    print_table(
        [
            ["COMMANDS", ""],
            ["new <name> <path>", "Create new source."],
            ["u <source>", "Update source."],
            [
                "u <source> f",
                "Force update source. Ignores even if no changes have been made.",
            ],
            ["ua", "Update all sources."],
            ["ua f", "Force update all sources."],
            ["rm <source>", "Delete source."],
            ["ls", "List all sources."],
            ["tree <source>", "List contents of source as a tree."],
            [
                "tree <source> <filename>",
                "Export contents of source as a tree to file.",
            ],
            ["rev <source>", "List all revisions of a source."],
            ["ig new <item>", "Add new item to ignore list."],
            ["ig rm <item>", "Remove item from ignore list."],
            ["ig ls", "List ignore list."],
            ["", ""],
            ["FLAGS", ""],
            ["-v", "Verbose."],
        ]
    )


def new(args):
    name = args[0]
    match = find(name)
    if match != None:
        print(f"Source already exists: {name}")
        return
    path = args[1]
    absolutePath = os.path.abspath(path)
    if not os.path.isdir(path):
        print(f"Invalid source path: {path}")
        return
    source = {
        "name": name,
        "path": absolutePath,
        "created": datetime.now().timestamp(),
        "updated": datetime.now().timestamp(),
        "revisions": 0,
    }
    source = traverse(source)
    source["checksum"] = checksum(source)
    mutate(
        f"INSERT INTO sources (name, value) VALUES ('{source['name']}', '{json.dumps(source)}');"
    )
    print(f"New source {name} added.")


def u(args, source=None):
    name = args[0]
    force = False
    if len(args) > 1 and args[1] == "f":
        force = True
    if source == None:
        (id, source) = find(name)
        if source == None:
            print(f"Source does not exist: {name}")
            return
    print(f"Checking {source['name']} for changes.")
    updated = traverse(source)
    if source == updated and not force:
        print(
            f"No changes to {source['name']} since {timestampToString(source['updated'])}"
        )
        return
    revision = {
        "sourceId": source["id"],
        "updated": source["updated"],
        "files": source["files"],
        "dirs": source["dirs"],
        "checksum": source["checksum"],
    }
    mutate(
        f"INSERT INTO revisions (sourceId, value) VALUES ({id}, '{json.dumps(revision)}');"
    )
    source["files"] = updated["files"]
    source["dirs"] = updated["dirs"]
    source["updated"] = datetime.now().timestamp()
    source["checksum"] = checksum(updated)
    mutate(f"UPDATE sources SET value = '{json.dumps(source)}' WHERE id = {id}")
    print(f"Updated {source['name']}.")


def ua(args=[""]):
    sources = query(f"SELECT value FROM sources")
    sources = ((json.loads(i[0])) for i in sources)
    for source in sources:
        u([source["name"], args[0]], source=source)


def traverse(parent):
    global data
    clone = copy.deepcopy(parent)
    clone["files"] = []
    clone["dirs"] = []
    for item in os.listdir(parent["path"]):
        if item in ig(["r"]):
            continue
        itemPath = os.path.join(parent["path"], item)
        if verbose:
            print(itemPath)
        if os.path.isfile(itemPath):
            filePath = itemPath
            stats = os.stat(filePath)
            clone["files"].append(
                {"name": item, "lastModified": stats.st_mtime, "size": stats.st_size}
            )
        elif os.path.isdir(itemPath):
            clone["dirs"].append(traverse({"name": item, "path": itemPath}))
    return clone


def ig(args):
    if args[0] == "new":
        value = args[1]
        mutate(f"INSERT INTO ignore (value) VALUES ('{value}')")
        ig(["ls"])
    elif args[0] == "rm":
        value = args[1]
        mutate(f"DELETE FROM ignore WHERE value = '{value}'")
        ig(["ls"])
    elif args[0] == "ls":
        ignoreList = query("SELECT value FROM ignore")
        ignoreList = [i[0] for i in ignoreList]
        print(ignoreList)
    elif args[0] == "r":
        ignoreList = query("SELECT value FROM ignore")
        ignoreList = [i[0] for i in ignoreList]
        return ignoreList


def rm(args):
    name = args[0]
    (id, source) = find(name)
    if source == None:
        print(f"Source does not exist: {name}")
        return
    mutate(f"DELETE FROM sources WHERE id = {id}")
    print(f"Source removed: {source['name']}")


def ls():
    sources = query("SELECT id, value FROM sources")
    sources = [(i[0], json.loads(i[1])) for i in sources]
    formatted = [
        [
            id,
            source["name"],
            source["path"],
            timestampToString(source["created"]),
            timestampToString(source["updated"]),
            revCount(id),
            sizeof_fmt(sizeCalc(source)),
        ]
        for (id, source) in sources
    ]
    formatted.insert(
        0, ["ID", "NAME", "PATH", "CREATED", "UPDATED", "REVISIONS", "SIZE"]
    )
    print_table(formatted)


def revCount(sourceId):
    count = query(f"SELECT count(*) FROM revisions WHERE sourceId = {sourceId}")
    count = count[0][0]
    return count


def rev(args):
    name = args[0]
    (id, source) = find(name)
    if source == None:
        print(f"Source does not exist: {name}")
        return
    formatted = []
    revisions = query(f"SELECT value FROM revisions WHERE sourceId = {id}")
    revisions = [json.loads(i[0]) for i in revisions]
    if len(revisions) > 0:
        formatted = [
            [
                len(revisions) - i - 1,
                timestampToString(revision["updated"]),
                sizeof_fmt(sizeCalc(revision)),
                revision["checksum"],
            ]
            for i, revision in enumerate(reversed(revisions))
        ]
    formatted.insert(
        0,
        [
            "current",
            timestampToString(source["updated"]),
            sizeof_fmt(sizeCalc(source)),
            source["checksum"],
        ],
    )
    formatted.insert(
        0,
        ["REVISION", "UPDATED", "SIZE", "CHECKSUM"],
    )
    sourceInfo(source)
    print_table(formatted)


def logSession(args):
    mutate(
        f"INSERT INTO logs (timestamp, commands) VALUES ({datetime.now().timestamp()}, '{' '.join(args)}');"
    )


def find(name):
    name = name[0]
    source = query(
        f"SELECT id, value FROM sources WHERE id = '{name}' OR name LIKE '%{name}%'"
    )
    if len(source) == 0:
        return None
    source = (source[0][0], json.loads(source[0][1]))
    return source


def tree(args):
    name = args[0]
    (_, source) = find(name)
    if source == None:
        print(f"Source does not exist: {name}")
        return
    lines = [i for i in treeGen(source)]
    if len(args) > 1:
        with open(args[1], "w", encoding="utf8") as f:
            f.write(f"{source['path']}\n")
            for line in lines:
                f.write(f"{line}\n")
        print(f"Tree for {source['name']} exported to {args[1]}")
    else:
        print(source["path"])
        for line in lines:
            print(line)


if __name__ == "__main__" and len(sys.argv) > 1:
    args = []
    for i in sys.argv[1:]:
        if i == "-v":
            verbose = True
        else:
            args.append(i)
    if len(args) == 1:
        globals()[args[0]]()
    else:
        globals()[args[0]](args[1:])
    logSession(args[2:])
    con.close()
else:
    guide()
