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

def upload_to_supabase(file_path, retries=3):
    import uuid
    ext = os.path.splitext(file_path)[1].lower() or ".jpg"
    for attempt in range(retries):
        try:
            safe_key = uuid.uuid4().hex + ext
            with open(file_path, "rb") as f:
                supabase.storage.from_("thai-fashion").upload(
                    path=safe_key,
                    file=f,
                    file_options={"content-type": "image/jpeg", "upsert": "true"},
                )
            return supabase.storage.from_("thai-fashion").get_public_url(safe_key)
        except Exception as e:
            print(f"Upload attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
    raise Exception(f"upload_to_supabase failed after {retries} attempts: {file_path}")

def get_IG_caption(image_path, retries=5):
    prompt = (
        "You are an Instagram copywriter for Tagifree, a brand specialising in custom iron-on patches & personalised DIY products, shipping WORLDWIDE.\n\n"
        "Your audience: people who LOVE iron-on patches and customising their own clothes, bags, jackets, hats & gifts. Speak to that passion.\n\n"
        "Write a SHORT, catchy English Instagram caption for the product shown in the image.\n\n"
        "Output this EXACT format, nothing else:\n"
        "\u2728 [catchy hook about the patch / customisation]\n"
        "\n"
        "[EXACTLY 1 line, max 12 words: one highlight that excites patch lovers & DIY fans + 1 emoji]\n"
        "\n"
        "\U0001f6cd\ufe0f Shop now on Etsy: tagifree.etsy.com\n"
        "\U0001f3a8 Want your own design? We offer full customisation \u2014 just tell us your idea.\n"
        "\U0001f4e6 Bulk orders welcome \u2014 DM us for wholesale & event pricing!\n"
        "#tagifree #irononpatches #custompatches #patchlover #patchgame #diyfashion #customembroidery #irononpatch #etsyshop #etsyseller [2 relevant product tags]\n\n"
        "STRICT RULES:\n"
        "- Description: 1 line only, 12 words max, must include 1 emoji\n"
        "- Keep the 3 action-hook lines (Shop / Custom / Bulk) and all hashtags EXACTLY as given\n"
        "- Replace [2 relevant product tags] with 2 fitting hashtags for this product\n"
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
    return "\u2728 Custom iron-on patches, made just for you \U0001f9f5\n\nIron on, stand out \u2014 your style, your patch \u2728\n\n\U0001f6cd\ufe0f Shop now on Etsy: tagifree.etsy.com\n\U0001f3a8 Want your own design? Full customisation available.\n\U0001f4e6 Bulk orders welcome \u2014 DM us for wholesale & event pricing!\n#tagifree #irononpatches #custompatches #patchlover #patchgame #diyfashion #customembroidery #etsyshop"

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
            files_str = "\n".join(file_names)
            msg = f"Tagifree published!\n\nImages:\n{files_str}\n\nMedia ID: {media_id}\n\nFeed: posted"
            send_telegram(msg)
        except Exception as e:
            print(f"Telegram notification failed: {e}")
    for name in file_names:
        try:
            supabase.storage.from_("thai-fashion").remove([name])
            print(f"Cleaned from Supabase: {name}")
        except Exception as e:
            print(f"Supabase delete failed for {name}: {e}")
        src = os.path.join(FOLDER_PATH, name)
        if os.path.exists(src):
            os.remove(src)
            print(f"Deleted from queue/: {name}")

# ================= MAIN =================

def main():
    files = sorted(f for f in os.listdir(FOLDER_PATH) if f.lower().endswith((".jpg", ".jpeg", ".png")))
    if not files:
        print("queue/ folder is empty - nothing to post")
        return
    posts = defaultdict(list)
    for f in files:
        match = re.match(r"(.+)[_-]\d+\.(jpg|jpeg|png)$", f.lower())
        prefix = match.group(1) if match else os.path.splitext(f)[0]
        posts[prefix].append(os.path.join(FOLDER_PATH, f))
    first_key = sorted(posts.keys(), key=lambda x: int(re.search(r'\d+', x).group()))[0]
    paths = sorted(posts[first_key])
    print(f"Single image: {os.path.basename(paths[0])}" if len(paths) == 1 else f"Carousel: {first_key} ({len(paths)} images)")
    urls = [upload_to_supabase(p) for p in paths]
    caption = get_IG_caption(paths[0])
    media_id = post_to_insta_and_story(urls, caption)
    notify_and_clean(media_id, [os.path.basename(p) for p in paths])

if __name__ == "__main__":
    main()
