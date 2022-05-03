import copy
import hashlib
import json
import os
from datetime import datetime

space = "    "
branch = "│   "
tee = "├── "
last = "└── "


def printTable(table):
    longest_cols = [
        (max([len(str(row[i])) for row in table]) + 3) for i in range(len(table[0]))
    ]
    row_format = "".join(
        ["{:<" + str(longest_col) + "}" for longest_col in longest_cols]
    )
    for row in table:
        print(row_format.format(*row))


def maxID(items):
    max = 0
    for item in items:
        if item["id"] > max:
            max = item["id"]
    return max


def timestampToString(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def sizeCalc(parent) -> int:
    size = 0
    for file in parent["files"]:
        size = size + file["size"]
    for dir in parent["dirs"]:
        size = size + sizeCalc(dir)
    return size


def sizeOfFmt(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


def treeGen(parent, prefix: str = ""):
    files = parent["files"]
    dirs = parent["dirs"]
    filePointers = ([tee] * (len(files) - 1)) + (
        [last] if len(parent["dirs"]) == 0 else [tee]
    )
    for pointer, file in zip(filePointers, files):
        yield prefix + pointer + file["name"]
    dirPointers = [tee] * (len(dirs) - 1) + [last]
    for pointer, dir in zip(dirPointers, dirs):
        yield prefix + pointer + dir["name"]
        extension = branch if pointer == tee else space
        yield from treeGen(dir, prefix=prefix + extension)


# def diffGen(rev1, rev2, prefix: str = ""):
#     fileAdditions = []
#     fileSubtractions = []
#     fileNames1 = [i["name"] for i in rev1["files"]]
#     fileNames2 = [i["name"] for i in rev2["files"]]
#     for file in fileNames1:
#         if file not in fileNames2:
#             fileAdditions.append(f"- {file}\n")
#     for file in fileNames2:
#         if file not in fileNames1:
#             fileSubtractions.append(f"+ {file}\n")
#     dirAdditions = []
#     dirSubtractions = []
#     dirNames1 = [i["name"] for i in rev1["dirs"]]
#     dirNames2 = [i["name"] for i in rev2["dirs"]]
#     for dir in dirNames1:
#         if dir not in dirNames2:
#             dirAdditions.append(f"- {dir}\n")
#     for dir in dirNames2:
#         if dir not in dirNames1:
#             dirSubtractions.append(f"+ {dir}\n")
#     fileAdditionPointers = [tee] * (len(fileAdditions) - 1) + [last]
#     for pointer, file in zip(fileAdditionPointers, fileAdditions):
#         yield prefix + pointer + file
#     fileSubtractionPointers = [tee] * (len(fileSubtractions) - 1) + [last]
#     for pointer, file in zip(fileSubtractionPointers, fileSubtractions):
#         yield prefix + pointer + file
#     dirAdditionPointers = [tee] * (len(dirAdditions) - 1) + [last]
#     for pointer, dir in zip(dirAdditionPointers, dirAdditions):
#         yield prefix + pointer + dir
#         extension = branch if pointer == tee else space
#         yield from diffGen(dir, prefix=prefix + extension)
#     dirSubtractionPointers = [tee] * (len(dirSubtractions) - 1) + [last]
#     for pointer, dir in zip(dirSubtractionPointers, dirSubtractions):
#         yield prefix + pointer + dir
#         extension = branch if pointer == tee else space
#         yield from diffGen(dir, prefix=prefix + extension)


def checksum(source):
    return hashlib.md5(
        json.dumps(
            source["files"] + source["dirs"], sort_keys=True, ensure_ascii=True
        ).encode("utf-8")
    ).hexdigest()


def sourceInfo(source):
    print(f"SOURCE: {source['name']}")


def traverse(parent, verbose=False, ignoreList=None):
    from dman import ig

    if ignoreList == None:
        ignoreList = ig(["r"])
    clone = copy.deepcopy(parent)
    clone["files"] = []
    clone["dirs"] = []
    for item in os.listdir(parent["path"]):
        try:
            if item in ignoreList:
                continue
            itemPath = os.path.join(parent["path"], item)
            if verbose:
                print(itemPath)
            if os.path.isfile(itemPath):
                filePath = itemPath
                stats = os.stat(filePath)
                clone["files"].append(
                    {
                        "name": item,
                        "lastModified": stats.st_mtime,
                        "size": stats.st_size,
                    }
                )
            elif os.path.isdir(itemPath):
                clone["dirs"].append(
                    traverse({"name": item, "path": itemPath}, verbose, ignoreList)
                )
        except PermissionError as e:
            print(e)
    return clone


def isInt(s):
    try:
        i = int(s)
        return True, i
    except ValueError:
        return False, s
