import os
import re
import time
import random
import requests
from collections import defaultdict
from supabase import create_client
from google import genai
from google.genai import types

# ================= ENV VARIABLES =================
SUPABASE_URL    = os.environ["SUPABASE_URL"]
SUPABASE_KEY    = os.environ["SUPABASE_KEY"]
GEMINI_KEY      = os.environ["GEMINI_KEY"]
IG_USER_ID      = os.environ["IG_USER_ID"]
INSTA_TOKEN     = os.environ["INSTA_TOKEN"]
TG_TOKEN        = os.environ.get("TG_TOKEN", "")
TG_CHAT_ID      = os.environ.get("TG_CHAT_ID", "")

# Images queued by the team live in queue/ inside the repo
FOLDER_PATH = os.path.join(os.path.dirname(__file__), "queue")

# ================= CLIENTS =================
supabase      = create_client(SUPABASE_URL, SUPABASE_KEY)
client_gemini = genai.Client(api_key=GEMINI_KEY)


# ================= CORE FUNCTIONS =================

def upload_to_supabase(file_path):
    import uuid
    ext = os.path.splitext(file_path)[1].lower() or ".jpg"
    safe_key = uuid.uuid4().hex + ext          # e.g. a3f8c2...jpg (no Chinese chars)
    with open(file_path, "rb") as f:
        supabase.storage.from_("thai-fashion").upload(
            path=safe_key,
            file=f,
            file_options={"content-type": "image/jpeg", "upsert": "true"},
        )
    return supabase.storage.from_("thai-fashion").get_public_url(safe_key)


def get_IG_caption(image_path, retries=5):
    prompt = (
        "\u4f60\u662f\u4e00\u4e2a\u4e13\u4e1a\u7684\u65f6\u5c1a\u5546\u4e1a\u5206\u6790\u5e08\u548c\u793e\u4ea4\u5a92\u4f53\u8fd0\u8425\u4e13\u5bb6\u3002\n\n"
        "\u4efb\u52a1\uff1a\u89c2\u5bdf\u56fe\u7247\u4e2d\u7684\u7ae5\u88c5\uff0c\u751f\u6210\u4e00\u6bb5\u5177\u5907\u9002\u5408\u4f20\u64ad\u5438\u5f15\u7c89\u4e1d\u7684 Instagram \u82f1\u6587\u6587\u6848\uff0c\u4f7f\u7528\u5408\u9002\u7684emoji\u3002\n\n"
        "\u6587\u6848\u4e60\u60ef\u5b9a\u5236\uff1a\n"
        "1. \u5f00\u5934\u7b2c\u4e00\u884c\uff1a\u75286SS NEW IN | \u5355\u54c1\u540d\u79f0 \u7684\u7ed3\u6784\u3002\n"
        "2. \u4e2d\u6bb5\uff1a\u7b80\u6d01\u660e\u4e86\u7684\u63cf\u8ff0\u8863\u670d\u8bbe\u8ba1\u4eae\u70b9\u3001\u98ce\u683c\uff08\u5355\u72ec\u4e00\u884c\uff09\uff0c\u9002\u5408\u4ec0\u4e48\u641c\u914d\u548c\u573a\u666f\uff08\u5355\u72ec\u4e00\u884c\uff09\u3002\n"
        "3. \u7ed3\u5c3e\uff1a\u5355\u72ec\u4e00\u884c\u5199\u660e \ud83d\uded9Shopee\uff1aTiny One Kids, \u518d\u81ea\u7136\u5f15\u5bfc\u5173\u6ce8\u6216\u70b9\u8d5e\u3002\n"
        "4. \u6807\u7b7e\uff1a\u5305\u542b #TINYONE #tinyoneth #ShopeeTH \u4ee5\u53ca 3 \u4e2a\u76f8\u5173\u6807\u7b7e\u3002\n\n"
        "DO NOT say 'Here is your caption' or 'Sure'."
    )
    for attempt in range(retries):
        try:
            with open(image_path, "rb") as f:
                img_bytes = f.read()
            response = client_gemini.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    prompt,
                    types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                ],
            )
            if response.text:
                return response.text
        except Exception as e:
            print(f"Gemini attempt {attempt + 1} failed: {e}")
            time.sleep((2 ** attempt) + random.random())
    print("Gemini failed after all retries - using fallback caption")
    return "New arrival Elegant & modern design."


def post_to_insta_and_story(urls, caption):
    try:
        if len(urls) == 1:
            print("Creating single-image Feed container")
            res = requests.post(
                f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media",
                data={"image_url": urls[0], "caption": caption, "access_token": INSTA_TOKEN},
            ).json()
        else:
            print("Creating carousel child containers")
            item_ids = []
            for url in urls:
                item = requests.post(
                    f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media",
                    data={"image_url": url, "is_carousel_item": "true", "access_token": INSTA_TOKEN},
                ).json()
                print("Carousel item:", item)
                if "id" not in item:
                    print("Child container creation failed")
                    return None
                item_ids.append(item["id"])
            print("Creating carousel parent container")
            res = requests.post(
                f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media",
                data={
                    "media_type": "CAROUSEL",
                    "children": ",".join(item_ids),
                    "caption": caption,
                    "access_token": INSTA_TOKEN,
                },
            ).json()

        print("Feed Container Response:", res)
        if "id" not in res:
            print("Feed container creation failed")
            return None

        creation_id = res["id"]
        print("Waiting for Instagram to process media...")
        time.sleep(8)

        publish_res = requests.post(
            f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media_publish",
            data={"creation_id": creation_id, "access_token": INSTA_TOKEN},
        ).json()
        print("Feed Publish Response:", publish_res)
        if "id" not in publish_res:
            print("Feed publish failed")
            return None

        published_media_id = publish_res["id"]
        print(f"Feed published: {published_media_id}")

        try:
            print("Publishing Story")
            story_container = requests.post(
                f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media",
                data={"image_url": urls[0], "media_type": "STORIES", "access_token": INSTA_TOKEN},
            ).json()
            print("Story Container:", story_container)
            if "id" in story_container:
                time.sleep(5)
                story_publish = requests.post(
                    f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media_publish",
                    data={"creation_id": story_container["id"], "access_token": INSTA_TOKEN},
                ).json()
                print("Story Publish:", story_publish)
                print("Story published" if "id" in story_publish else "Story publish failed")
            else:
                print("Story container creation failed")
        except Exception as story_error:
            print(f"Story error: {story_error}")

        return published_media_id

    except Exception as e:
        print(f"Unexpected error: {e}")
        return None


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": str(TG_CHAT_ID).strip(), "text": message}
    try:
        res = requests.post(url, data=payload, timeout=10)
        print("Telegram Status:", res.status_code)
        return res.json()
    except Exception as e:
        print(f"Telegram error: {e}")
        return None


def notify_and_clean(media_id, file_names):
    print(f"Instagram publish success! Media ID: {media_id}")
    if TG_TOKEN and TG_CHAT_ID:
        try:
            msg = f"Tiny One published!\n\nMedia ID: {media_id}\n\nFeed: posted\nStory: posted"
            send_telegram(msg)
        except Exception as e:
            print(f"Telegram notification failed: {e}")

    for name in file_names:
        try:
            supabase.storage.from_("thai-fashion").remove([name])
            print(f"Cleaned from Supabase: {name}")
        except Exception as e:
            print(f"Delete failed for {name}: {e}")

    posted_dir = os.path.join(FOLDER_PATH, "..", "posted")
    os.makedirs(posted_dir, exist_ok=True)
    for name in file_names:
        src = os.path.join(FOLDER_PATH, name)
        dst = os.path.join(posted_dir, name)
        if os.path.exists(src):
            os.rename(src, dst)
            print(f"Moved to posted/: {name}")


# ================= MAIN =================

def main():
    files = sorted(
        f for f in os.listdir(FOLDER_PATH) if f.lower().endswith((".jpg", ".png"))
    )
    if not files:
        print("queue/ folder is empty - nothing to post")
        return

    posts = defaultdict(list)
    for f in files:
        match = re.match(r"(.+)_\d+\.(jpg|png)$", f.lower())
        prefix = match.group(1) if match else os.path.splitext(f)[0]
        posts[prefix].append(os.path.join(FOLDER_PATH, f))

    first_key = sorted(posts.keys())[0]
    paths = sorted(posts[first_key])

    print(
        f"Single image: {os.path.basename(paths[0])}"
        if len(paths) == 1
        else f"Carousel: {first_key} ({len(paths)} images)"
    )

    urls     = [upload_to_supabase(p) for p in paths]
    caption  = get_IG_caption(paths[0])
    media_id = post_to_insta_and_story(urls, caption)

    if media_id:
        notify_and_clean(media_id, [os.path.basename(p) for p in paths])


if __name__ == "__main__":
    main()
