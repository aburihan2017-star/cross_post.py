import json
import os
import time
from beemblurt import Blurt
import requests

HIVE_USERNAME = os.getenv("HIVE_USERNAME", "aburihan1")
BLURT_USERNAME = os.getenv("BLURT_USERNAME", "aburihan1")
BLURT_POSTING_KEY = os.getenv("BLURT_POSTING_KEY")

COMMUNITY_TAG = "blurt-1787181"


def get_hive_posts(username, limit=15):
    url = "https://api.hive.blog"
    payload = {
        "jsonrpc": "2.0",
        "method": "condenser_api.get_discussions_by_blog",
        "params": [{"tag": username, "limit": limit}],
        "id": 1,
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        data = res.json().get("result", [])
        return [post for post in data if post.get("author") == username]
    except Exception as e:
        print(f"Hive API Error: {e}")
        return []


def is_already_on_blurt(username, permlink):
    url = "https://rpc.blurt.world"
    payload = {
        "jsonrpc": "2.0",
        "method": "condenser_api.get_content",
        "params": [username, permlink],
        "id": 1,
    }

    try:
        res = requests.post(url, json=payload, timeout=5)
        data = res.json().get("result", {})
        if data and data.get("author") == username:
            return True
    except Exception as e:
        print(f"Blurt Check Error: {e}")

    return False


def cross_post_unshared_posts():
    if not BLURT_POSTING_KEY:
        print("Error: BLURT_POSTING_KEY পাওয়া যায়নি!")
        return

    posts = get_hive_posts(HIVE_USERNAME, limit=15)

    if not posts:
        print("কোনো Hive পোস্ট পাওয়া যায়নি।")
        return

    blurt_nodes = [
        "https://rpc.blurt.world",
        "https://blurt-rpc.saboin.com",
        "https://kentuckycrypto.com",
    ]
    blurt = Blurt(node=blurt_nodes, keys=[BLURT_POSTING_KEY])

    posted_count = 0

    for hive_post in reversed(posts):
        title = hive_post.get("title")
        body = hive_post.get("body")
        permlink = hive_post.get("permlink")
        hive_url = f"https://hive.blog{hive_post.get('url')}"

        if is_already_on_blurt(BLURT_USERNAME, permlink):
            print(f"⏭️ স্কিপ করা হলো (ইতিমধ্যে Blurt-এ আছে): '{title}'")
            continue

        print(f"\n🚀 Blurt-এ নতুন পোস্ট শেয়ার হচ্ছে: '{title}'...")

        footer = (
            f"\n\n---\n*Originally published on Hive: [{title}]({hive_url})*"
        )
        blurt_body = body + footer
        tags = [COMMUNITY_TAG, "blurt", "hive"]

        try:
            blurt.post(
                title=title,
                body=blurt_body,
                author=BLURT_USERNAME,
                tags=tags,
                permlink=permlink,
            )
            print(f"✅ সফলভাবে Blurt-এ শেয়ার হয়েছে: '{title}'\n")
            posted_count += 1
            time.sleep(3)
        except Exception as e:
            print(f"❌ এরর: {e}\n")

    print(f"\nকাজ শেষ! মোট {posted_count} টি নতুন পোস্ট Blurt-এ শেয়ার হয়েছে।")


if __name__ == "__main__":
    cross_post_unshared_posts()
