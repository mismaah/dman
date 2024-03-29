import subprocess
import os
import sqlite3
import sys
import json
import uuid
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
            [
                "tree <source or revision id>",
                "List contents of source or revision as a tree.",
            ],
            [
                "tree <source> <filename>",
                "Export source tree to file.",
            ],
            ["rev <source>", "List all revisions of a source."],
            ["ig new <item>", "Add new item to ignore list."],
            ["ig rm <item>", "Remove item from ignore list."],
            ["ig ls", "List ignore list."],
            [
                "b <source> <destination path>",
                "Backup source by making source and destionation identical, modifying destination only.",
            ],
            ["bh <sourc>", "List backup history of source."],
            ["", ""],
            ["FLAGS", ""],
            ["-v", "Verbose."],
        ]
    )


def new(args):
    name = args[0]
    path = args[1]
    absolutePath = os.path.abspath(path)
    if not os.path.isdir(path):
        print(f"Invalid source path: {path}")
        return
    source = {
        "path": absolutePath,
    }
    source = helpers.traverse(source, verbose=verbose)
    revisionId = str(uuid.uuid4())
    try:
        database.mutate(
            "INSERT INTO sources (name, path, created, current_revision_id) VALUES (?, ?, ?, ?)",
            params=(name, absolutePath, datetime.now().timestamp(), revisionId),
        )
    except sqlite3.IntegrityError:
        print("Source already exists.")
        return
    database.mutate(
        "INSERT INTO revisions (id, sourceId, created, checksum, value) VALUES (?, ?, ?, ?, ?)",
        params=(
            revisionId,
            database.cur.lastrowid,
            datetime.now().timestamp(),
            helpers.checksum(source),
            json.dumps(source, ensure_ascii=True),
        ),
    )
    print(f"New source {name} added.")


def u(args):
    name = args[0]
    force = False
    if len(args) > 1 and args[1] == "f":
        force = True
    (source, revision) = database.find(name)
    current = revision["value"]
    if source == None:
        print(f"Source does not exist: {name}")
        return
    id = source["id"]
    print(f"Checking {source['name']} for changes.")
    updated = helpers.traverse(current, verbose=verbose)
    if current == updated and not force:
        print(
            f"No changes to {source['name']} since {helpers.timestampToString(source['created'])}"
        )
        return
    revisionId = str(uuid.uuid4())
    database.mutate(
        "INSERT INTO revisions (id, sourceId, created, checksum, value) VALUES (?, ?, ?, ?, ?)",
        params=(
            revisionId,
            id,
            datetime.now().timestamp(),
            helpers.checksum(updated),
            json.dumps(updated, ensure_ascii=True),
        ),
    )
    database.mutate(
        "UPDATE sources SET current_revision_id = ? WHERE id = ?",
        params=(revisionId, id),
    )
    print(f"Updated {source['name']}.")


def ua(args=[""]):
    sources = database.fetch(f"SELECT id FROM sources")
    sources = (i[0] for i in sources)
    for source in sources:
        u([source, args[0]])


def ig(args):
    if args[0] == "new":
        value = args[1]
        try:
            database.mutate("INSERT INTO ignore (value) VALUES (?)", params=((value,)))
            ig(["ls"])
        except sqlite3.IntegrityError:
            print(f"{value} is already in the ignore list.")
    elif args[0] == "rm":
        value = args[1]
        database.mutate("DELETE FROM ignore WHERE value = ?", params=((value,)))
        ig(["ls"])
    elif args[0] == "ls":
        ignoreList = database.fetch("SELECT value FROM ignore")
        ignoreList = [i[0] for i in ignoreList]
        print(ignoreList)
    elif args[0] == "r":
        ignoreList = database.fetch("SELECT value FROM ignore")
        ignoreList = [i[0] for i in ignoreList]
        return ignoreList


def rm(args):
    name = args[0]
    (source, _) = database.find(name)
    if source == None:
        print(f"Source does not exist: {name}")
        return
    database.mutate("DELETE FROM sources WHERE id = ?", params=((source["id"],)))
    database.mutate(
        "DELETE FROM revisions WHERE sourceId = ?", params=((source["id"],))
    )
    print(f"Source removed: {source['name']}")


def ls():
    sources = database.fetch(
        """SELECT sources.id, name, sources.created, current_revision_id, revisions.value, revisions.created FROM sources
        LEFT JOIN revisions ON sources.current_revision_id = revisions.id"""
    )
    formatted = [
        [
            id,
            name,
            helpers.timestampToString(created),
            database.revCount(id),
            helpers.sizeOfFmt(helpers.sizeCalc(json.loads(value))),
            helpers.timestampToString(updated),
        ]
        for [id, name, created, current_revision_id, value, updated] in sources
    ]
    formatted.insert(
        0,
        ["ID", "NAME", "CREATED", "REVISIONS", "SIZE", "UPDATED"],
    )
    helpers.printTable(formatted)


def rev(args):
    name = args[0]
    (source, current) = database.find(name)
    if source == None:
        print(f"Source does not exist: {name}")
        return
    id = source["id"]
    formatted = []
    revisions = database.fetch(
        "SELECT id, created, checksum, value FROM revisions WHERE sourceId = ? ORDER BY created DESC",
        params=((id,)),
    )
    if len(revisions) > 0:
        revisions = [(i[0], i[1], i[2], json.loads(i[3])) for i in revisions]
        if len(revisions) > 0:
            formatted = [
                [
                    "*" if current["id"] == id else "",
                    len(revisions) - i - 1,
                    id,
                    helpers.timestampToString(created),
                    helpers.sizeOfFmt(helpers.sizeCalc(revision)),
                    checksum,
                ]
                for i, [id, created, checksum, revision] in enumerate(revisions)
            ]
    formatted.insert(
        0,
        ["CURRENT", "REVISION", "ID", "CREATED", "SIZE", "CHECKSUM"],
    )
    helpers.sourceInfo(source)
    helpers.printTable(formatted)


def tree(args):
    name = args[0]
    sourceAndRevision = database.find(name)
    source = None
    current = None
    if sourceAndRevision == None:
        revMatchAndSource = database.findRev(name)
        if revMatchAndSource == None:
            print(f"Source or revision does not exist: {name}")
            return
        (revision, source) = revMatchAndSource
        current = revision["value"]
    else:
        (source, revision) = sourceAndRevision
        current = revision["value"]
    lines = [i for i in helpers.treeGen(current)]
    printName = f"Source: {source['name']}"
    if sourceAndRevision == None:
        printName += f"\t Revision: {name}"
    if len(args) > 1:
        with open(args[1], "w", encoding="utf8") as f:
            f.write(f"{source['path']}\n")
            for line in lines:
                f.write(f"{line}\n")
        print(f"Tree for {source['name']} exported to {args[1]}")
    else:
        print(printName)
        print(source["path"])
        for line in lines:
            print(line)


# def diff(args):
#     revId1 = args[0]
#     revId2 = args[1]
#     rev1 = database.findRev(revId1)
#     if rev1 == None:
#         print(f"First revision provided does not exist. ID: {revId1}")
#         return
#     rev2 = database.findRev(revId2)
#     if rev2 == None:
#         print(f"Second revision provided does not exist. ID: {revId2}")
#         return
#     if rev1["sourceId"] != rev2["sourceId"]:
#         print("Revisions are not from the same source.")
#     lines = helpers.diffGen(rev1["value"], rev2["value"])
#     for line in lines:
#         print(line)


def b(args):
    name = args[0]
    path = args[1]
    (source, revision) = database.find(name)
    if source == None:
        print(f"Source does not exist: {name}")
        return
    if not os.path.isdir(path):
        print(f"Invalid destination path: {path}")
        return
    subprocess.run(
        f"rclone/rclone.exe sync {source['path']} {path} -i {'-v' if verbose else ''}"
    )
    database.mutate(
        "INSERT INTO backups (sourceId, revisionId, created, destination) VALUES (?, ?, ?, ?)",
        params=(source["id"], revision["id"], datetime.now().timestamp(), path),
    )


def bh(args):
    name = args[0]
    (source, _) = database.find(name)
    if source == None:
        print(f"Source does not exist: {name}")
        return
    backups = database.fetch(
        """
    SELECT revisionId, created, destination
    FROM backups WHERE sourceId = ?
    ORDER BY created DESC
    """,
        params=(source["id"],),
    )
    formatted = [
        [
            revisionId,
            destination,
            helpers.timestampToString(created),
        ]
        for [revisionId, created, destination] in backups
    ]
    formatted.insert(
        0,
        ["REVISION", "DESTINATION", "CREATED"],
    )
    print("Backup history")
    helpers.sourceInfo(source)
    helpers.printTable(formatted)


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
        database.logSession(sys.argv[1:])
        database.con.close()
