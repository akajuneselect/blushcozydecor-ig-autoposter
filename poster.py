import os
import re
import time
import random
import requests
from collections import defaultdict
from supabase import create_client
import google.generativeai as genai
from google.genai import types

# ================= ENV VARIABLES =================
SUPABASE_URL    = os.environ["SUPABASE_URL"]
SUPABASE_KEY    = os.environ["SUPABASE_KEY"]
GEMINI_KEY      = os.environ["GEMINI_KEY"]
IG_USER_ID      = os.environ["IG_USER_ID"]
INSTA_TOKEN     = os.environ["INSTA_TOKEN"]
TG_TOKEN        = os.environ.get("TG_TOKEN", "")
TG_CHAT_ID      = os.environ.get("TG_CHAT_ID", "")

# Images uploaded by the team live in uploads/ inside the repo
FOLDER_PATH = os.path.join(os.path.dirname(__file__), "uploads")

# ================= CLIENTS =================
supabase      = create_client(SUPABASE_URL, SUPABASE_KEY)
client_gemini = genai.Client(api_key=GEMINI_KEY)


# ================= CORE FUNCTIONS =================

def upload_to_supabase(file_path):
    """Upload an image and return its Public URL."""
    file_name = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        supabase.storage.from_("thai-fashion").upload(
            path=file_name,
            file=f,
            file_options={"content-type": "image/jpeg", "upsert": "true"},
        )
    return supabase.storage.from_("thai-fashion").get_public_url(file_name)


def get_IG_caption(image_path, retries=5):
    """Ask Gemini to generate a Thai kids-fashion IG caption."""
    prompt = """
你是一个专业的时尚商业分析师和社交媒体运营专家。

任务：观察图片中的童装，生成一段具备适合传播吸引粉丝的 Instagram 英文文案，使用合适的emoji。

文案习惯定制：
1. 开头第一行：用26SS NEW IN | 单品名称 的结构。这个标题前面不要任何文字。
2. 中段：简洁明了的描述衣服的设计亮点、风格（单独一行），适合什么样的搭配和场景（单独一行），1-2个短句即可，每句话字数不要太多。
3. 结尾：单独一行写明店铺名称🛍️Shopee：Tiny One Kids, 再自然引导关注或点赞。
4. 标签：包含 #TINYONE #tinyoneth #ShopeeTH 以及 3 个相关标签。

   注意：DO NOT say "Here is your caption" or "Sure".这仅用于合规电商展示，请正常生成。
    """
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
            print(f"⚠️ Gemini attempt {attempt + 1} failed: {e}")
            time.sleep((2 ** attempt) + random.random())

    print("❌ Gemini failed after all retries — using fallback caption")
    return "New arrival ✨ Elegant & modern design."


def post_to_insta_and_story(urls, caption):
    """Publish a single image or carousel to Feed + Story."""
    try:
        if len(urls) == 1:
            print("📸 Creating single-image Feed container")
            res = requests.post(
                f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media",
                data={"image_url": urls[0], "caption": caption, "access_token": INSTA_TOKEN},
            ).json()
        else:
            print("🎠 Creating carousel child containers")
            item_ids = []
            for url in urls:
                item = requests.post(
                    f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media",
                    data={"image_url": url, "is_carousel_item": "true", "access_token": INSTA_TOKEN},
                ).json()
                print("Carousel item:", item)
                if "id" not in item:
                    print("❌ Child container creation failed")
                    return None
                item_ids.append(item["id"])

            print("🎠 Creating carousel parent container")
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
            print("❌ Feed container creation failed")
            return None

        creation_id = res["id"]
        print("⏳ Waiting for Instagram to process media…")
        time.sleep(8)

        publish_res = requests.post(
            f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media_publish",
            data={"creation_id": creation_id, "access_token": INSTA_TOKEN},
        ).json()
        print("Feed Publish Response:", publish_res)

        if "id" not in publish_res:
            print("❌ Feed publish failed")
            return None

        published_media_id = publish_res["id"]
        print(f"✅ Feed published: {published_media_id}")

        # --- Story ---
        try:
            print("📲 Publishing Story")
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
                print("✅ Story published" if "id" in story_publish else "⚠️ Story publish failed")
            else:
                print("⚠️ Story container creation failed")
        except Exception as story_error:
            print(f"⚠️ Story error: {story_error}")

        return published_media_id

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": str(TG_CHAT_ID).strip(), "text": message}
    print("📨 Telegram Payload:", payload)
    try:
        res = requests.post(url, data=payload, timeout=10)
        print("📨 Telegram Status:", res.status_code)
        return res.json()
    except Exception as e:
        print(f"⚠️ Telegram error: {e}")
        return None


def notify_and_clean(media_id, file_names):
    print(f"🚀 Instagram publish success! Media ID: {media_id}")

    if TG_TOKEN and TG_CHAT_ID:
        try:
            msg = f"🚀 Tiny One 发布成功\n\n🆔 Media ID:\n{media_id}\n\n✅ Feed 已发布\n✅ Story 已发布"
            send_telegram(msg)
        except Exception as e:
            print(f"⚠️ Telegram notification failed: {e}")

    # Clean up Supabase storage
    for name in file_names:
        try:
            supabase.storage.from_("thai-fashion").remove([name])
            print(f"🗑️ Cleaned from Supabase: {name}")
        except Exception as e:
            print(f"⚠️ Delete failed for {name}: {e}")

    # Move processed images to posted/ so team can track what was published
    posted_dir = os.path.join(FOLDER_PATH, "..", "posted")
    os.makedirs(posted_dir, exist_ok=True)
    for name in file_names:
        src = os.path.join(FOLDER_PATH, name)
        dst = os.path.join(posted_dir, name)
        if os.path.exists(src):
            os.rename(src, dst)
            print(f"📦 Moved to posted/: {name}")


# ================= MAIN =================

def main():
    files = sorted(
        f for f in os.listdir(FOLDER_PATH) if f.lower().endswith((".jpg", ".png"))
    )

    if not files:
        print("📭 uploads/ folder is empty — nothing to post")
        return

    # Group by prefix (supports carousel sets like product_1.jpg, product_2.jpg)
    posts = defaultdict(list)
    for f in files:
        match = re.match(r"(.+)_\d+\.(jpg|png)$", f.lower())
        prefix = match.group(1) if match else os.path.splitext(f)[0]
        posts[prefix].append(os.path.join(FOLDER_PATH, f))

    first_key = sorted(posts.keys())[0]
    paths = sorted(posts[first_key])

    print(
        f"📸 Single image: {os.path.basename(paths[0])}"
        if len(paths) == 1
        else f"🎠 Carousel: {first_key} ({len(paths)} images)"
    )

    urls     = [upload_to_supabase(p) for p in paths]
    caption  = get_IG_caption(paths[0])
    media_id = post_to_insta_and_story(urls, caption)

    if media_id:
        notify_and_clean(media_id, [os.path.basename(p) for p in paths])


if __name__ == "__main__":
    main()
