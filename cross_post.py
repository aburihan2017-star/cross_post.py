from datetime import datetime, timedelta, timezone
import json
import os
import sys
import time
import requests
from beem import Blurt

# আপনার ইউজারনেম ও এনভায়রনমেন্ট ভেরিয়েবল
HIVE_USERNAME = os.getenv("HIVE_USERNAME", "aburihan1")
BLURT_USERNAME = os.getenv("BLURT_USERNAME", "aburihan1")
BLURT_POSTING_KEY = os.getenv("BLURT_POSTING_KEY")

COMMUNITY_TAG = "blurt-1787181"
DAYS_AGO = 365  # ১ বছর (৩৬৫ দিন) আগের সময়সীমা

# Blurt-এর সচল ও সক্রিয় RPC নোডসমূহ
BLURT_NODES = [
    "https://rpc.beblurt.com",
    "https://blurt-rpc.saboin.com",
    "https://rpc.blurt.live",
    "https://kentuckyludwig.com"
]


def get_hive_posts(username, days=DAYS_AGO):
    """নির্দিষ্ট দিন (যেমন ৩৬৫ দিন) আগের সময় থেকে আজকের দিকে আসা পোস্টসমূহ সংগ্রহ করা"""
    url = "https://api.hive.blog"
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    print(f"--- গত {days} দিন আগের ({cutoff_date.strftime('%Y-%m-%d')}) পর থেকে পোস্ট খোঁজা শুরু হচ্ছে... ---")

    all_posts = []
    start_author = None
    start_permlink = None

    while True:
        params = {"account": username, "sort": "posts", "limit": 20}
        if start_author and start_permlink:
            params["start_author"] = start_author
            params["start_permlink"] = start_permlink

        payload = {
            "jsonrpc": "2.0",
            "method": "bridge.get_account_posts",
            "params": params,
            "id": 1,
        }

        try:
            res = requests.post(url, json=payload, timeout=10)
            data = res.json().get("result", [])

            if not data:
                break

            if start_permlink:
                data = data[1:]  # আগের পেজের শেষ আইটেম বাদ দেওয়া

            if not data:
                break

            stop_fetching = False
            for post in data:
                if post.get("author") != username:
                    continue

                created_str = post.get("created")
                created_dt = datetime.fromisoformat(created_str).replace(tzinfo=timezone.utc)

                # যদি পোস্টটি ১ বছরের আগের পুরোনো হয়, তবে ফেচিং বন্ধ করবে
                if created_dt < cutoff_date:
                    stop_fetching = True
                    break

                all_posts.append(post)

                start_author = post.get("author")
                start_permlink = post.get("permlink")

            if stop_fetching or len(data) < 19:
                break

        except Exception as e:
            print(f"Hive Fetch Error: {e}")
            break

    # পোস্টগুলোকে পুরোনো থেকে নতুন ক্রমানুসারে সাজানো (Oldest to Newest)
    all_posts.sort(key=lambda x: x.get("created"))
    print(f"গত {days} দিনের সীমার মধ্যে মোট {len(all_posts)} টি পোস্ট পাওয়া গেছে।")
    return all_posts


def is_already_on_blurt(username, permlink):
    """ব্লার্টে পোস্টটি আগেই প্রকাশ করা হয়েছে কিনা তা একাধিক সচল নোডে চেক করা"""
    payload = {
        "jsonrpc": "2.0",
        "method": "condenser_api.get_content",
        "params": [username, permlink],
        "id": 1,
    }

    for node in BLURT_NODES:
        try:
            res = requests.post(node, json=payload, timeout=5)
            if res.status_code == 200:
                result = res.json().get("result", {})
                if result and result.get("author") == username and result.get("permlink") == permlink:
                    return True
                return False
        except Exception:
            continue
    return False


def publish_to_blurt(post):
    """বিম (beem) লাইব্রেরি দিয়ে ব্লার্টে পোস্ট তৈরি করা"""
    if not BLURT_POSTING_KEY:
        print("❌ Error: BLURT_POSTING_KEY পাওয়া যায়নি! GitHub Secrets চেক করুন।")
        sys.exit(1)

    title = post.get("title", "")
    body = post.get("body", "")
    permlink = post.get("permlink", "")

    # ট্যাগ প্রোসেসিং
    json_metadata = post.get("json_metadata", {})
    if isinstance(json_metadata, str):
        try:
            json_metadata = json.loads(json_metadata)
        except Exception:
            json_metadata = {}

    tags = json_metadata.get("tags", [])
    if COMMUNITY_TAG not in tags:
        tags.insert(0, COMMUNITY_TAG)

    blurt_instance = None
    for node in BLURT_NODES:
        try:
            blurt_instance = Blurt(node=node, keys=[BLURT_POSTING_KEY])
            break
        except Exception:
            continue

    if not blurt_instance:
        print("❌ Error: ব্লার্টের কোনো নোডের (Node) সাথেই যুক্ত হওয়া সম্ভব হয়নি!")
        sys.exit(1)

    try:
        print(f"🚀 Blurt-এ পাবলিশ করা হচ্ছে: '{title}'...")
        blurt_instance.post(
            title=title,
            body=body,
            author=BLURT_USERNAME,
            permlink=permlink,
            tags=tags,
            self_vote=False
        )
        print("✅ সফলভাবে Blurt-এ পোস্ট তৈরি হয়েছে! 🚀")
        return True
    except Exception as e:
        print(f"❌ Blurt Publish Error: {e}")
        # পোস্ট যদি আগে থেকেই থেকে থাকে
        if "already" in str(e).lower() or "permlink" in str(e).lower():
            print("⚠️ পোস্টটি আগে থেকেই ব্লার্টে বিদ্যমান।")
            return False
        sys.exit(1)


def main():
    if not BLURT_POSTING_KEY:
        print("❌ Error: GitHub Secrets-এ 'BLURT_POSTING_KEY' খুঁজে পাওয়া যায়নি।")
        sys.exit(1)

    # ১. ১ বছর (৩৬৫ দিন) আগের পোস্ট থেকে শুরু করে তালিকা সংগ্রহ করা
    posts = get_hive_posts(HIVE_USERNAME, days=DAYS_AGO)

    if not posts:
        print(f"ℹ️ গত {DAYS_AGO} দিনের মধ্যে শেয়ার করার মতো কোনো পোস্ট পাওয়া যায়নি।")
        return

    # ২. পুরোনো পোস্ট থেকে একটি একটি করে চেক করা
    posted = False
    for post in posts:
        permlink = post.get("permlink")
        title = post.get("title")

        print(f"\nপোস্ট চেক করা হচ্ছে: '{title}'")

        # ব্লার্টে আগেই আছে কিনা দেখা
        if is_already_on_blurt(BLURT_USERNAME, permlink):
            print("⏩ এই পোস্টটি ব্লার্টে আগেই শেয়ার করা হয়েছে। স্কিপ করা হচ্ছে...")
            continue

        # নতুন পোস্ট পাওয়া গেলে ব্লার্টে প্রকাশ করা
        if publish_to_blurt(post):
            posted = True
            print("\n🎉 আজকের দিনের ১টি পোস্ট সফলভাবে ব্লার্টে শেয়ার হয়েছে। সেশন সম্পন্ন!")
            break  # দিনে মাত্র ১টি পোস্ট শেয়ার করে রান বন্ধ করবে

    if not posted:
        print(f"\nℹ️ গত {DAYS_AGO} দিনের সব পোস্টই ব্লার্টে ইতিমধ্যে পোস্ট করা আছে। নতুন কোনো পোস্ট শেয়ার করা হয়নি।")


if __name__ == "__main__":
    main()
