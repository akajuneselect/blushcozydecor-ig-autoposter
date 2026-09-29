import mimetypes
import os
import random
import re
import time
import uuid
from collections import defaultdict

import requests
from google import genai
from google.genai import types
from supabase import create_client


FOLDER_PATH = os.path.join(os.path.dirname(__file__), "queue")
DRY_RUN = os.environ.get("DRY_RUN", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
GRAPH_API_VERSION = os.environ.get("GRAPH_API_VERSION", "v21.0").strip() or "v21.0"

supabase = None
client_gemini = None
IG_USER_ID = ""
INSTA_TOKEN = ""
TG_TOKEN = ""
TG_CHAT_ID = ""


def natural_key(value):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def image_mime_type(file_path):
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type if mime_type in {"image/jpeg", "image/png"} else "image/jpeg"


def initialize_clients():
    global supabase, client_gemini, IG_USER_ID, INSTA_TOKEN, TG_TOKEN, TG_CHAT_ID

    required_names = [
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "GEMINI_KEY",
        "IG_USER_ID",
        "INSTA_TOKEN",
    ]
    missing = [name for name in required_names if not os.environ.get(name, "").strip()]
    if missing:
        raise RuntimeError(
            "Missing required GitHub Actions secrets: " + ", ".join(missing)
        )

    supabase = create_client(
        os.environ["SUPABASE_URL"].strip(), os.environ["SUPABASE_KEY"].strip()
    )
    client_gemini = genai.Client(api_key=os.environ["GEMINI_KEY"].strip())
    IG_USER_ID = os.environ["IG_USER_ID"].strip()
    INSTA_TOKEN = os.environ["INSTA_TOKEN"].strip()
    TG_TOKEN = os.environ.get("TG_TOKEN", "").strip()
    TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "").strip()


def upload_to_supabase(file_path, retries=3):
    assert supabase is not None, "Supabase client is not initialized"
    extension = os.path.splitext(file_path)[1].lower() or ".jpg"
    mime_type = image_mime_type(file_path)

    for attempt in range(retries):
        remote_key = f"instagram/{uuid.uuid4().hex}{extension}"
        try:
            with open(file_path, "rb") as image_file:
                supabase.storage.from_("home-decor").upload(
                    path=remote_key,
                    file=image_file,
                    file_options={
                        "content-type": mime_type,
                        "upsert": "false",
                    },
                )
            public_url = supabase.storage.from_("home-decor").get_public_url(remote_key)
            return public_url, remote_key
        except Exception as error:
            print(f"Upload attempt {attempt + 1} failed: {error}")
            try:
                supabase.storage.from_("home-decor").remove([remote_key])
            except Exception:
                pass
            if attempt < retries - 1:
                time.sleep(3 * (attempt + 1))

    raise RuntimeError(f"Supabase upload failed after {retries} attempts: {file_path}")


def get_ig_caption(image_path, retries=5):
    assert client_gemini is not None, "Gemini client is not initialized"
    prompt = (
        "You are an Instagram + Pinterest copywriter for Blush Pages, a brand "
        "specialising in Coquette Stationery for Journals & Planners✍🏻📓 Washi tapes, planner goodies & cozy finds, shipping "
        "WORLDWIDE.\n\n"
        "warm, cozy home.\n\n"
        "Write a short English caption for the product in the image. Output exactly:\n"
        "✨ [catchy hook]\n\n"
        "[1-2 natural sentences, maximum 30 words, with 2-3 searchable keywords and "
        "one emoji]\n\n"
        "🛍️ Shop now on Amazon & Etsy: blushpagesnz \n"
        "#blushpages #JournalWithMe #JunkJournalSupplies #CoquetteStationery #JournalingCommunity"
        "[1 relevant product tag]\n\n"
        "Do not add an introduction, outro, or extra lines."
    )

    for attempt in range(retries):
        try:
            with open(image_path, "rb") as image_file:
                image_bytes = image_file.read()
            response = client_gemini.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    prompt,
                    types.Part.from_bytes(
                        data=image_bytes, mime_type=image_mime_type(image_path)
                    ),
                ],
            )
            if response.text:
                return response.text.strip()
        except Exception as error:
            print(f"Gemini attempt {attempt + 1} failed: {error}")
            if attempt < retries - 1:
                time.sleep((2**attempt) + random.random())

    print("Gemini failed after all retries; using fallback caption")
    return (
        "✨ Cozy home & table decor, styled with love 🪷\n\n"
        "Beautiful tablescape pieces to style your dining table and warm up your home ✨\n\n"
        "🛍️ Shop now on Etsy: blushcozydecor.etsy.com\n"
        "🎨 Want a custom look? We offer full styling — just tell us your vibe.\n"
        "📦 Bulk & event orders welcome — DM us for wholesale & event pricing!\n"
        "#blushcozydecor #tabledecor #homedecor #tablescape #cozyhome #diningtable"
    )


def graph_post(endpoint, data):
    response = requests.post(
        f"https://graph.facebook.com/{GRAPH_API_VERSION}/{endpoint}",
        data=data,
        timeout=60,
    )
    try:
        return response.json()
    except ValueError as error:
        raise RuntimeError(
            f"Instagram API returned HTTP {response.status_code} without JSON"
        ) from error


def require_graph_id(payload, operation):
    if "id" not in payload:
        raise RuntimeError(f"Instagram {operation} failed: {payload}")
    return payload["id"]


def post_to_instagram(urls, caption):
    if len(urls) == 1:
        print("Creating single-image feed container")
        container = graph_post(
            f"{IG_USER_ID}/media",
            {
                "image_url": urls[0],
                "caption": caption,
                "access_token": INSTA_TOKEN,
            },
        )
    else:
        print("Creating carousel child containers")
        child_ids = []
        for url in urls:
            child = graph_post(
                f"{IG_USER_ID}/media",
                {
                    "image_url": url,
                    "is_carousel_item": "true",
                    "access_token": INSTA_TOKEN,
                },
            )
            child_ids.append(require_graph_id(child, "carousel child creation"))

        print("Creating carousel parent container")
        container = graph_post(
            f"{IG_USER_ID}/media",
            {
                "media_type": "CAROUSEL",
                "children": ",".join(child_ids),
                "caption": caption,
                "access_token": INSTA_TOKEN,
            },
        )

    creation_id = require_graph_id(container, "container creation")
    print("Waiting for Instagram to process media")
    time.sleep(8)

    last_response = None
    for attempt in range(5):
        last_response = graph_post(
            f"{IG_USER_ID}/media_publish",
            {"creation_id": creation_id, "access_token": INSTA_TOKEN},
        )
        if "id" in last_response:
            print(f"Feed published: {last_response['id']}")
            return last_response["id"]
        if attempt < 4:
            print(f"Publish attempt {attempt + 1} not ready: {last_response}")
            time.sleep(5 * (attempt + 1))

    raise RuntimeError(f"Instagram publish failed: {last_response}")


def send_telegram(message):
    if not (TG_TOKEN and TG_CHAT_ID):
        return
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data={"chat_id": TG_CHAT_ID, "text": message},
            timeout=15,
        )
        print(f"Telegram status: {response.status_code}")
    except Exception as error:
        print(f"Telegram notification failed: {error}")


def cleanup_supabase(remote_keys):
    assert supabase is not None, "Supabase client is not initialized"
    for remote_key in remote_keys:
        try:
            supabase.storage.from_("home-decor").remove([remote_key])
            print(f"Cleaned from Supabase: {remote_key}")
        except Exception as error:
            print(f"Supabase cleanup failed for {remote_key}: {error}")


def group_queue_files(files):
    posts = defaultdict(list)
    for file_name in files:
        match = re.match(r"(.+?)[_-](\d+)\.(jpg|jpeg|png)$", file_name, re.IGNORECASE)
        prefix = match.group(1) if match else os.path.splitext(file_name)[0]
        posts[prefix].append(os.path.join(FOLDER_PATH, file_name))
    return posts


def main():
    files = sorted(
        (
            file_name
            for file_name in os.listdir(FOLDER_PATH)
            if file_name.lower().endswith((".jpg", ".jpeg", ".png"))
        ),
        key=natural_key,
    )
    if not files:
        print("queue/ is empty; nothing to post")
        return

    posts = group_queue_files(files)
    first_key = sorted(posts, key=natural_key)[0]
    paths = sorted(posts[first_key], key=lambda path: natural_key(os.path.basename(path)))
    file_names = [os.path.basename(path) for path in paths]
    post_type = "single image" if len(paths) == 1 else f"carousel ({len(paths)} images)"
    print(f"Selected {post_type}: {', '.join(file_names)}")

    if DRY_RUN:
        print("DRY RUN: no external APIs called; queue/ is unchanged")
        return

    initialize_clients()
    uploaded_urls = []
    remote_keys = []
    try:
        for path in paths:
            public_url, remote_key = upload_to_supabase(path)
            uploaded_urls.append(public_url)
            remote_keys.append(remote_key)

        caption = get_ig_caption(paths[0])
        media_id = post_to_instagram(uploaded_urls, caption)
    except Exception:
        cleanup_supabase(remote_keys)
        print("Publish failed; queue/ files were preserved")
        raise

    send_telegram(
        "blushcozydecor published!\n\n"
        f"Images:\n{chr(10).join(file_names)}\n\n"
        f"Media ID: {media_id}\n\nFeed: posted"
    )
    cleanup_supabase(remote_keys)

    for path in paths:
        os.remove(path)
        print(f"Deleted from queue/: {os.path.basename(path)}")


if __name__ == "__main__":
    main()
