# 🛍️ Tiny One IG Auto-Poster

> **GitHub Actions + Supabase Storage + Gemini AI** — fully automated Instagram posting pipeline for Tiny One Kids.

---

## 📐 Architecture (3 Physical Stages)

```
┌─────────────────────────────────────────────────────────┐
│  Stage 1 · TRIGGER                                      │
│  GitHub Actions fires on:                               │
│   • push to uploads/ (team drops images)                │
│   • schedule: 10 AM Bangkok time (03:00 UTC) daily      │
│   • workflow_dispatch (manual run from Actions tab)     │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│  Stage 2 · STORAGE RELAY (Supabase)                     │
│  poster.py uploads images from uploads/ to              │
│  Supabase bucket "thai-fashion" → gets public CDN URL   │
│  Instagram API requires a public HTTPS URL              │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│  Stage 3 · DATA LOOP CLOSURE                            │
│  • Instagram Feed published (single or carousel)        │
│  • Instagram Story published                            │
│  • Supabase file deleted (cleanup)                      │
│  • Image moved: uploads/ → posted/                      │
│  • Telegram notification sent                           │
│  • Git commit moves processed files back to repo        │
└─────────────────────────────────────────────────────────┘
```

---

## 🔑 Required GitHub Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret name | Where to get it |
|---|---|
| `SUPABASE_URL` | Supabase → Project Settings → API → Project URL |
| `SUPABASE_KEY` | Supabase → Project Settings → API → service_role key |
| `GEMINI_KEY` | Google AI Studio → Get API key |
| `IG_USER_ID` | Instagram Graph API → your IG Business Account ID |
| `INSTA_TOKEN` | Meta for Developers → long-lived access token |
| `TG_TOKEN` | *(optional)* BotFather → bot token |
| `TG_CHAT_ID` | *(optional)* your Telegram chat/group ID |

---

## 👥 Team Workflow: How to Upload & Post

### Option A — Upload via GitHub UI (no Git needed)

1. Go to the repo → **uploads/** folder
2. Click **Add file → Upload files**
3. Drag & drop your `.jpg` or `.png` images
4. Scroll down → click **Commit changes** (commit to `main`)
5. ✅ The push to `uploads/` automatically triggers the Action!

### Option B — Upload via Git

```bash
git clone git@github.com:Leoahboom/tiny-one-ig-autoposter.git
cd tiny-one-ig-autoposter

# Copy your images into uploads/
cp ~/Desktop/product_shot.jpg uploads/

git add uploads/
git commit -m "add: product_shot for today's post"
git push origin main
# → GitHub Actions fires automatically
```

---

## 📁 Naming Convention

| Pattern | Result |
|---|---|
| `dress.jpg` | Single image post |
| `dress_1.jpg`, `dress_2.jpg`, `dress_3.jpg` | Carousel (3-slide) |

Images are processed in alphabetical order. The **first prefix group** in the folder is posted each run.

---

## ⏰ Schedule

The bot runs automatically at **10:00 AM Bangkok time** (UTC+7) every day.

To change the time, edit the `cron` line in `.github/workflows/post.yml`:
```yaml
- cron: "0 3 * * *"   # 03:00 UTC = 10:00 AM BKK
```

---

## 🕹️ Manual Run

Go to **Actions → 🚀 Post to Instagram → Run workflow** to trigger immediately.
You can set `dry_run: true` to test without actually publishing.

---

## 📊 What Happens After Posting

| Item | Action |
|---|---|
| Image in Supabase | Deleted (cleanup) |
| Image in `uploads/` | Moved to `posted/` |
| Instagram Feed | Published ✅ |
| Instagram Story | Published ✅ |
| Telegram | Notification sent ✅ |

---

## 🗂️ File Structure

```
tiny-one-ig-autoposter/
├── .github/
│   └── workflows/
│       └── post.yml          ← GitHub Actions workflow
├── uploads/                  ← ⬅️ Team drops images HERE
│   └── .gitkeep
├── posted/                   ← Published images land here
│   └── .gitkeep
├── poster.py                 ← Main Python script
├── requirements.txt          ← Python dependencies
└── README.md                 ← This file
```
# tiny-one-ig-autoposter
Instagram auto-posting bot: GitHub Actions + Supabase storage + Gemini AI captions
