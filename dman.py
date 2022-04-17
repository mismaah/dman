import os
import sys
import json
import copy
from datetime import datetime
from helpers import *

dataFileName = "data.json"
data = {"sources": [], "log": [], "ignore": []}


def load():
    global data
    try:
        with open(dataFileName, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Data file not found.")
        createFile()


def save():
    global data
    with open(dataFileName, "w") as f:
        json.dump(data, f, indent=2)


def createFile():
    print("Creating new data file.")
    with open(dataFileName, "w") as f:
        json.dump(data, f)


def guide():
    print_table(
        [
            ["Commands", ""],
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
            ["h <source>", "List all revisions of a source."],
            ["ignore new <item>", "Add new item to ignore list."],
            ["ignore rm <item>", "Remove item from ignore list."],
            ["ignore ls", "List ignore list."],
        ]
    )


def new(args):
    global data
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
        "id": maxID(data["sources"]) + 1,
        "name": name,
        "path": absolutePath,
        "created": datetime.now().timestamp(),
        "updated": datetime.now().timestamp(),
        "revisions": 0,
    }
    source = traverse(source)
    source["checksum"] = checksum(source)
    data["sources"].append(source)
    print(f"New source {name} added.")


def u(args):
    global data
    name = args[0]
    force = False
    if len(args) > 1 and args[1] == "f":
        force = True
    source = find(name)
    if source == None:
        print(f"Source does not exist: {name}")
        return
    updated = traverse(source)
    if source == updated and not force:
        print(
            f"No changes to {source['name']} since {timestampToString(source['updated'])}"
        )
        return
    if not "history" in source:
        source["history"] = []
    source["history"].append(
        {
            "updated": source["updated"],
            "files": source["files"],
            "dirs": source["dirs"],
            "checksum": source["checksum"],
        }
    )
    source["files"] = updated["files"]
    source["dirs"] = updated["dirs"]
    source["updated"] = datetime.now().timestamp()
    source["revisions"] = updated["revisions"] + 1
    source["checksum"] = checksum(updated)
    print(f"Updated {source['name']}.")


def ua(args=[""]):
    global data
    for source in data["sources"]:
        u([source["name"], args[0]])


def traverse(parent):
    global data
    clone = copy.deepcopy(parent)
    clone["files"] = []
    clone["dirs"] = []
    for item in os.listdir(parent["path"]):
        if item in data["ignore"]:
            continue
        itemPath = os.path.join(parent["path"], item)
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


def ignore(args):
    global data
    if args[0] == "new":
        data["ignore"].append(args[1])
        data["ignore"] = list(set(data["ignore"]))
    elif args[0] == "rm":
        data["ignore"] = [item for item in data["ignore"] if item != args[1]]
    elif args[0] == "ls":
        print(data["ignore"])


def rm(args):
    global data
    name = args[0]
    source = find(name)
    if source == None:
        print(f"Source does not exist: {name}")
        return
    data["sources"] = [
        source for source in data["sources"] if source["name"] != source["name"]
    ]
    print(f"Source removed: {source['name']}")


def ls():
    global data
    formatted = [
        [
            source["id"],
            source["name"],
            source["path"],
            timestampToString(source["created"]),
            timestampToString(source["updated"]),
            source["revisions"],
            sizeof_fmt(sizeCalc(source)),
        ]
        for source in data["sources"]
    ]
    formatted.insert(
        0, ["ID", "NAME", "PATH", "CREATED", "UPDATED", "REVISIONS", "SIZE"]
    )
    print_table(formatted)


def h(args):
    global data
    name = args[0]
    source = find(name)
    if source == None:
        print(f"Source does not exist: {name}")
        return
    formatted = []
    if "history" in source:
        formatted = [
            [
                len(source["history"]) - i - 1,
                timestampToString(history["updated"]),
                sizeof_fmt(sizeCalc(history)),
                history["checksum"],
            ]
            for i, history in enumerate(reversed(source["history"]))
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
    global data
    data["log"].append({"timestamp": datetime.now().timestamp(), "commands": args})


def find(name):
    global data
    match = next(
        (source for source in data["sources"] if source["name"] == name),
        None,
    )
    if match == None:
        try:
            match = next(
                (source for source in data["sources"] if source["id"] == int(name)),
                None,
            )
        except ValueError:
            pass
    return match


def tree(args):
    global data
    name = args[0]
    source = find(name)
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
    load()
    args = sys.argv[2:]
    if len(args) == 0:
        globals()[sys.argv[1]]()
    else:
        globals()[sys.argv[1]](args)
    logSession(sys.argv[1:])
    save()
else:
    guide()
