from datetime import datetime, timedelta, timezone
import json
import os
import sys
import time
from beem import Blurt
import requests

# আপনার ইউজারনেম
HIVE_USERNAME = os.getenv("HIVE_USERNAME", "aburihan1")
BLURT_USERNAME = os.getenv("BLURT_USERNAME", "aburihan1")
BLURT_POSTING_KEY = os.getenv("BLURT_POSTING_KEY")

COMMUNITY_TAG = "blurt-1787181"
DAYS_AGO = 365  # ১ বছর আগের সময়সীমা (৩৬৫ দিন)


def get_hive_posts_from_one_year_ago(username, days=365):
    """১ বছর আগের সময় থেকে শুরু করে পোস্ট সংগ্রহ করা"""
    url = "https://api.hive.blog"
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    print(
        f"--- {days} দিন আগের ({cutoff_date.strftime('%Y-%m-%d')}) থেকে পোস্ট খোঁজা শুরু হচ্ছে... ---"
    )

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

            for post in data:
                if post.get("author") != username:
                    continue

                created_str = post.get("created")
                created_dt = datetime.fromisoformat(created_str).replace(
                    tzinfo=timezone.utc
                )

                all_posts.append(post)

                start_author = post.get("author")
                start_permlink = post.get("permlink")

                # ১ বছর আগের সীমা অতিক্রম করলে থামবে
                if created_dt < cutoff_date:
                    break

            last_post_created = datetime.fromisoformat(
                data[-1].get("created")
            ).replace(tzinfo=timezone.utc)
            if last_post_created < cutoff_date or len(data) < 19:
                break

        except Exception as e:
            print(f"Hive Fetch Error: {e}")
            break

    # ১ বছর আগের পুরোনো পোস্টগুলোকে সবার সামনে এনে ক্রমানুসারে সাজানো (Oldest to Newest)
    all_posts.sort(key=lambda x: x.get("created"))
    print(
        f"১ বছর আগের সীমার মধ্যে মোট {len(all_posts)} টি পোস্ট পাওয়া গেছে।"
    )
    return all_posts


def is_already_on_blurt(username, permlink):
    """ব্লার্টে পোস্টটি আগেই প্রকাশ করা হয়েছে কিনা চেক করা"""
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
        if (
            data
            and data.get("author") == username
            and data.get("permlink") == permlink
        ):
            return True
    except Exception as e:
        print(f"Blurt Check Warning: {e}")

    return False


def process_and_post_unshared():
    if not BLURT_POSTING_KEY:
        print("❌ Error: BLURT_POSTING_KEY পাওয়া যায়নি! সিক্রেট কি চেক করুন।")
        sys.exit(1)

    # ১ বছর আগের পোস্ট সংগ্রহ করা
    posts = get_hive_posts_from_one_year_ago(HIVE_USERNAME, days=DAYS_AGO)

    if not posts:
        print("❌ কোনো পোস্ট পাওয়া যায়নি।")
        return

    blurt_nodes = [
        "https://rpc.blurt.world",
        "https://blurt-rpc.saboin.com",
        "https://rpc.beblurt.com",
    ]
    blurt = Blurt(node=blurt_nodes, keys=[BLURT_POSTING_KEY])

    posted_count = 0
    MAX_POSTS_PER_RUN = 3  # ব্লকচেইন লিমিট এড়াতে প্রতিবার সর্বোচ্চ ৩ টি নতুন পোস্ট শেয়ার করবে

    for hive_post in posts:
        title = hive_post.get("title")
        body = hive_post.get("body")
        permlink = hive_post.get("permlink")
        created = hive_post.get("created")
        hive_url = f"https://hive.blog{hive_post.get('url')}"

        print(f"\n[তারিখ: {created}] পোস্ট চেক করা হচ্ছে: '{title}'")

        # ১. ব্লার্টে চেক করা
        if is_already_on_blurt(BLURT_USERNAME, permlink):
            print(
                f"⏭️ অলরেডি Blurt-এ পাবলিশ করা আছে। পরবর্তী (Next) পোস্টে যাওয়া হচ্ছে..."
            )
            continue

        # ২. ব্লার্টে পাবলিশ না থাকলে নতুন করে ব্লার্টে পাঠানো
        print(f"🚀 Blurt-এ পাবলিশ করা হচ্ছে: '{title}'...")

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
            print(f"✅ সফলভাবে Blurt-এ পোস্ট তৈরি হয়েছে! 🎉\n")
            posted_count += 1
            time.sleep(5)  # প্রতিটি পোস্টের পর ৫ সেকেন্ড বিরতি

            # প্রতিবারে লিমিট বজায় রাখা
            if posted_count >= MAX_POSTS_PER_RUN:
                print(
                    f"⚠️ এই সেশনে {MAX_POSTS_PER_RUN} টি আন-শেয়ার্ড পোস্ট সফলভাবে ব্লার্টে শেয়ার হয়েছে। বাকিগুলো পরের রান-এ অটো হবে।"
                )
                break

        except Exception as e:
            print(f"❌ পোস্ট করার সময় এরর: {e}\n")

    print(
        f"\n=== সমাপ্ত: এই রান-এ মোট {posted_count} টি নতুন পোস্ট Blurt-এ শেয়ার হলো ==="
    )


if __name__ == "__main__":
    process_and_post_unshared()
