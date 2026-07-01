# 🕯️ blushcozydecor IG Auto-Poster

GitHub Actions + Supabase Storage + Gemini AI — fully automated Instagram posting pipeline for **blushcozydecor** (cozy home & table decor).

## 📐 Architecture (3 Physical Stages)

```
┌─────────────────────────────────────────────────────────┐
│ Stage 1 · TRIGGER                                        │
│ GitHub Actions fires on:                                │
│   • push to queue/ (team drops images)                  │
│   • schedule: 11 AM & 7 PM Auckland time daily          │
│   • workflow_dispatch (manual run from Actions tab)     │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│ Stage 2 · STORAGE RELAY (Supabase)                      │
│ poster.py uploads images from queue/ to                 │
│ Supabase bucket "home-decor" → gets public CDN URL      │
│ Instagram API requires a public HTTPS URL               │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│ Stage 3 · DATA LOOP CLOSURE                             │
│   • Instagram Feed published (single or carousel)       │
│   • Supabase file deleted (cleanup)                     │
│   • Image removed from queue/                           │
│   • Telegram notification sent                          │
│   • Git commit records processed files back to repo     │
└─────────────────────────────────────────────────────────┘
```

## 🔑 Required GitHub Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret name | Where to get it |
|---|---|
| SUPABASE_URL | Supabase → Project Settings → API → Project URL |
| SUPABASE_KEY | Supabase → Project Settings → API → service_role key |
| GEMINI_KEY | Google AI Studio → Get API key |
| IG_USER_ID | Instagram Graph API → your IG Business Account ID |
| INSTA_TOKEN | Meta for Developers → long-lived access token |
| TG_TOKEN (optional) | BotFather → bot token |
| TG_CHAT_ID (optional) | your Telegram chat/group ID |

## 👥 Team Workflow: How to Upload & Post

### Option A — Upload via GitHub UI (no Git needed)

1. Go to the repo → **queue/** folder
2. Click **Add file → Upload files**
3. Drag & drop your **.jpg** or **.png** images
4. Scroll down → click **Commit changes** (commit to main)

✅ The push to queue/ automatically triggers the Action!

### Option B — Upload via Git

```bash
git clone git@github.com:akajuneselect/blushcozydecor-ig-autoposter.git
cd blushcozydecor-ig-autoposter

# Copy your images into queue/
cp ~/Desktop/table_setting.jpg queue/

git add queue/
git commit -m "add: table_setting for today's post"
git push origin main
# → GitHub Actions fires automatically
```

## 📁 Naming Convention

| Pattern | Result |
|---|---|
| candle.jpg | Single image post |
| candle_1.jpg, candle_2.jpg, candle_3.jpg | Carousel (3-slide) |

Images are processed in alphabetical order. The first prefix group in the folder is posted each run.

## ⏰ Schedule

The bot runs automatically at **11:00 AM & 7:00 PM Auckland time (UTC+12/+13)** every day.

To change the times, edit the cron lines in `.github/workflows/post.yml`:

```yaml
- cron: "0 23 * * *"   # 11:00 AM Auckland
- cron: "0 7 * * *"    # 7:00 PM Auckland
```

## 🕹️ Manual Run

Go to **Actions → Post to Instagram → Run workflow** to trigger immediately. You can set `dry_run: true` to test without actually publishing.

## 📊 What Happens After Posting

| Item | Action |
|---|---|
| Image in Supabase | Deleted (cleanup) |
| Image in queue/ | Removed |
| Instagram Feed | Published ✅ |
| Telegram | Notification sent ✅ |

## 🗂️ File Structure

```
blushcozydecor-ig-autoposter/
├── .github/
│   └── workflows/
│       └── post.yml        ← GitHub Actions workflow
├── queue/                  ← ⬅️ Team drops images HERE
│   └── .gitkeep
├── uploads/                ← (legacy) alternate upload folder
│   └── .gitkeep
├── poster.py               ← Main Python script
├── requirements.txt        ← Python dependencies
└── README.md               ← This file
```

---

**blushcozydecor** — Instagram auto-posting bot: GitHub Actions + Supabase storage + Gemini AI captions
