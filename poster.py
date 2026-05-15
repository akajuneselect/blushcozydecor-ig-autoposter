import os
import io
import re
import time
import random
import requests
from collections import defaultdict
from PIL import Image, ImageFilter
from supabase import create_client
from google import genai
from google.genai import types

# ================= ENV VARIABLES =================
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
GEMINI_KEY = os.environ["GEMINI_KEY"]
IG_USER_ID = os.environ["IG_USER_ID"]
INSTA_TOKEN = os.environ["INSTA_TOKEN"]
TG_TOKEN = os.environ.get("TG_TOKEN", "")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "")

# Images queued by the team live in queue/ inside the repo
FOLDER_PATH = os.path.join(os.path.dirname(__file__), "queue")

# ================= CLIENTS =================
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client_gemini = genai.Client(api_key=GEMINI_KEY)

# ================= CORE FUNCTIONS =================


def make_story_image(image_path):
    """Resize image to 1080x1920 for Stories using blurred background."""
    STORY_W, STORY_H = 1080, 1920
    img = Image.open(image_path).convert("RGB")
    bg = img.copy()
    bg_ratio = max(STORY_W / bg.width, STORY_H / bg.height)
    bg = bg.resize(
        (int(bg.width * bg_ratio), int(bg.height * bg_ratio)),
        Image.LANCZOS,
    )
    left = (bg.width - STORY_W) // 2
    top = (bg.height - STORY_H) // 2
    bg = bg.crop((left, top, left + STORY_W, top + STORY_H))
    bg = bg.filter(ImageFilter.GaussianBlur(radius=30))
    PAD = 80
    max_w = STORY_W - PAD * 2
    max_h = STORY_H - PAD * 2
    fg_ratio = min(max_w / img.width, max_h / img.height)
    fg = img.resize(
        (int(img.width * fg_ratio), int(img.height * fg_ratio)),
        Image.LANCZOS,
    )
    x = (STORY_W - fg.width) // 2
    y = (STORY_H - fg.height) // 2
    bg.paste(fg, (x, y))
    buf = io.BytesIO()
    bg.save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return buf


def upload_to_supabase(file_path):
        import uuid
        ext = os.path.splitext(file_path)[1].lower() or ".jpg"
        safe_key = uuid.uuid4().hex + ext
        with open(file_path, "rb") as f:
                    supabase.storage.from_("thai-fashion").upload(
                                    path=safe_key,
                                    file=f,
                                    file_options={"content-type": "image/jpeg", "upsert": "true"},
                    )
                return supabase.storage.from_("thai-fashion").get_public_url(safe_key)


def upload_bytes_to_supabase(buf, suffix="_story.jpg"):
        import uuid
    safe_key = uuid.uuid4().hex + suffix
    supabase.storage.from_("thai-fashion").upload(
                path=safe_key,
                file=buf,
                file_options={"content-type": "image/jpeg", "upsert": "true"},
    )
    return supabase.storage.from_("thai-fashion").get_public_url(safe_key)


def get_IG_caption(image_path, retries=5):
        prompt = (
            "You are an Instagram copywriter for Tiny One Kids, a Thai children's fashion brand.\n\n"
            "Write a SHORT English Instagram caption for the kids' outfit shown.\n\n"
            "Output this EXACT format, nothing else:\n"
            "26SS NEW IN | [product name]\n"
            "\n"
            "[EXACTLY 1 line, max 10 words: one design highlight + one emoji]\n"
            "\n"
            "\U0001F6CD \U0001d598\U0001d589\U0001d594\U0001d595\U0001d58a\U0001d58a: \U0001d4e3\U0001d4f2\U0001d4f7\U0001d4e8 \U0001d4de\U0001d4f7\U0001d4ea \U0001d4da\U0001d4f2\U0001d4ed\U0001d4fc\n"
            "\n"
            "#TINYONE #tinyoneth #ShopeeTH [3 relevant tags]\n\n"
            "STRICT RULES:\n"
            "- Description: 1 line only, 10 words max, must include 1 emoji\n"
            "- The \U0001F6CD emoji MUST appear exactly as written before Shopee\n"
            "- Blank line after title and before description is required\n"
            "- No intro, no outro, no extra lines, no 'Here is' or 'Sure'"
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


def post_to_insta_and_story(urls, caption, first_image_path):
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
                        print("Creating Story image (1080x1920)...")
            story_buf = make_story_image(first_image_path)
            story_url = upload_bytes_to_supabase(story_buf)
            print(f"Story image uploaded: {story_url}")
            story_container = requests.post(
                                f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media",
                                data={"image_url": story_url, "media_type": "STORIES", "access_token": INSTA_TOKEN},
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
                match = re.match(r"(.+)[_-]\d+\.(jpg|png)$", f.lower())
        prefix = match.group(1) if match else os.path.splitext(f)[0]
        posts[prefix].append(os.path.join(FOLDER_PATH, f))

    first_key = sorted(posts.keys())[0]
    paths = sorted(posts[first_key])

    print(
                f"Single image: {os.path.basename(paths[0])}"
                if len(paths) == 1
                else f"Carousel: {first_key} ({len(paths)} images)"
    )

    urls = [upload_to_supabase(p) for p in paths]
    caption = get_IG_caption(paths[0])
    media_id = post_to_insta_and_story(urls, caption, paths[0])

    if media_id:
                notify_and_clean(media_id, [os.path.basename(p) for p in paths])


if __name__ == "__main__":
        main()
