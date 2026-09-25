#!/home/cloud/microflow_server/bin/python
import json
import os
from collections import Counter
from datafed.CommandLib import API

def query_collection_recursive(df_api, coll_id, extensions, depth=0):
    total_records = 0
    total_size_bytes = 0
    offset = 0
    count = 100

    while True:
        try:
            result = df_api.collectionItemsList(coll_id, offset=offset, count=count)
            items = result[0].item
        except Exception as e:
            print(f"  [warn] Could not list collection {coll_id}: {e}")
            break

        if not items:
            break

        for item in items:
            if item.id.startswith("d/"):
                total_records += 1
                try:
                    view = df_api.dataView(item.id)
                    record = view[0].data[0]
                    size = record.size or 0
                    total_size_bytes += size
                    # Extract file extension from title
                    title = record.title or ""
                    ext = os.path.splitext(title)[1].lower()
                    if ext:
                        extensions[ext] += 1
                    else:
                        extensions["no_extension"] += 1
                except Exception as e:
                    print(f"  [warn] Could not get info for {item.id}: {e}")

            elif item.id.startswith("c/"):
                print(f"  {'  '*depth}-> Entering sub-collection: {item.id}")
                sub_records, sub_size = query_collection_recursive(
                    df_api, item.id, extensions, depth+1)
                total_records += sub_records
                total_size_bytes += sub_size

        offset += count
        if len(items) < count:
            break

    return total_records, total_size_bytes


def query_repo_stats():
    config_path = "/home/cloud/cnms-qr-sample-tracking-main/config.json"
    with open(config_path, "r") as f:
        config_data = json.load(f)

    context = config_data["datafed"].get("context", "").strip()
    root_collection = "c/p_cnms_root"

    df_api = API()
    if context:
        df_api.setContext(context)

    print(f"Querying collection recursively: {root_collection}\n")

    extensions = Counter()
    total_records, total_size_bytes = query_collection_recursive(
        df_api, root_collection, extensions)

    total_size_gb = total_size_bytes / (1024 ** 3)

    print(f"\nTotal records: {total_records}")
    print(f"Total data size: {total_size_gb:.2f} GB")
    print(f"\nFile extensions found:")
    for ext, count in extensions.most_common():
        print(f"  {ext}: {count} files")

if __name__ == "__main__":
    query_repo_stats()