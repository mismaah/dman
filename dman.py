import os
import sys
import json
import helpers
import database
from datetime import datetime


verbose = False


def help():
    helpers.printTable(
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
                "Export source tree to file.",
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
    match = database.find(name)
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
    source = helpers.traverse(source, verbose=verbose)
    source["checksum"] = helpers.checksum(source)
    database.mutate(
        "INSERT INTO sources (name, value) VALUES (?, ?);",
        params=(source["name"], json.dumps(source, ensure_ascii=True)),
    )
    print(f"New source {name} added.")


def u(args, idsource=None):
    name = args[0]
    force = False
    if len(args) > 1 and args[1] == "f":
        force = True
    id = None
    source = None
    if source == None:
        (id, source) = database.find(name)
        if source == None:
            print(f"Source does not exist: {name}")
            return
    else:
        (id, source) = idsource
    print(f"Checking {source['name']} for changes.")
    updated = helpers.traverse(source, verbose=verbose)
    if source == updated and not force:
        print(
            f"No changes to {source['name']} since {helpers.timestampToString(source['updated'])}"
        )
        return
    revision = {
        "sourceId": id,
        "updated": source["updated"],
        "files": source["files"],
        "dirs": source["dirs"],
        "checksum": source["checksum"],
    }
    database.mutate(
        "INSERT INTO revisions (sourceId, value) VALUES (?, ?);",
        params=(id, json.dumps(revision, ensure_ascii=True)),
    )
    source["files"] = updated["files"]
    source["dirs"] = updated["dirs"]
    source["updated"] = datetime.now().timestamp()
    source["checksum"] = helpers.checksum(updated)
    database.mutate(
        "UPDATE sources SET value = ? WHERE id = ?",
        params=(json.dumps(source, ensure_ascii=True), id),
    )
    print(f"Updated {source['name']}.")


def ua(args=[""]):
    sources = database.query(f"SELECT id, value FROM sources")
    sources = ((i[0], (json.loads(i[1]))) for i in sources)
    for source in sources:
        u([source[1]["name"], args[0]], idsource=source)


def ig(args):
    if args[0] == "new":
        value = args[1]
        database.mutate("INSERT INTO ignore (value) VALUES (?)", params=(value))
        ig(["ls"])
    elif args[0] == "rm":
        value = args[1]
        database.mutate("DELETE FROM ignore WHERE value = ?", params=(value))
        ig(["ls"])
    elif args[0] == "ls":
        ignoreList = database.query("SELECT value FROM ignore")
        ignoreList = [i[0] for i in ignoreList]
        print(ignoreList)
    elif args[0] == "r":
        ignoreList = database.query("SELECT value FROM ignore")
        ignoreList = [i[0] for i in ignoreList]
        return ignoreList


def rm(args):
    name = args[0]
    (id, source) = database.find(name)
    if source == None:
        print(f"Source does not exist: {name}")
        return
    database.mutate("DELETE FROM sources WHERE id = ?", params=((id,)))
    print(f"Source removed: {source['name']}")


def ls():
    sources = database.query("SELECT id, value FROM sources")
    sources = [(i[0], json.loads(i[1])) for i in sources]
    formatted = [
        [
            id,
            source["name"],
            source["path"],
            helpers.timestampToString(source["created"]),
            helpers.timestampToString(source["updated"]),
            database.revCount(id),
            helpers.sizeOfFmt(helpers.sizeCalc(source)),
        ]
        for (id, source) in sources
    ]
    formatted.insert(
        0, ["ID", "NAME", "PATH", "CREATED", "UPDATED", "REVISIONS", "SIZE"]
    )
    helpers.printTable(formatted)


def rev(args):
    name = args[0]
    (id, source) = database.find(name)
    if source == None:
        print(f"Source does not exist: {name}")
        return
    formatted = []
    revisions = database.query(
        "SELECT value FROM revisions WHERE sourceId = ?", params=((id,))
    )
    revisions = [json.loads(i[0]) for i in revisions]
    if len(revisions) > 0:
        formatted = [
            [
                len(revisions) - i - 1,
                helpers.timestampToString(revision["updated"]),
                helpers.sizeOfFmt(helpers.sizeCalc(revision)),
                revision["checksum"],
            ]
            for i, revision in enumerate(reversed(revisions))
        ]
    formatted.insert(
        0,
        [
            "current",
            helpers.timestampToString(source["updated"]),
            helpers.sizeOfFmt(helpers.sizeCalc(source)),
            source["checksum"],
        ],
    )
    formatted.insert(
        0,
        ["REVISION", "UPDATED", "SIZE", "CHECKSUM"],
    )
    helpers.sourceInfo(source)
    helpers.printTable(formatted)


def tree(args):
    name = args[0]
    (_, source) = database.find(name)
    if source == None:
        print(f"Source does not exist: {name}")
        return
    lines = [i for i in helpers.treeGen(source)]
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


if __name__ == "__main__":
    if len(sys.argv) == 1:
        help()
    else:
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
        database.logSession(args[2:])
        database.con.close()
