# 🕯️ blushcozydecor IG Auto-Poster

GitHub Actions + Supabase Storage + Gemini AI pipeline for scheduled Instagram feed posts.

## How it works

1. Add `.jpg`, `.jpeg`, or `.png` images to `queue/`.
2. GitHub Actions runs daily at 11:00 AM and 7:00 PM in `Pacific/Auckland` time.
3. The script selects the first filename group, uploads it temporarily to Supabase, creates a Gemini caption, and publishes it to Instagram.
4. Only after Instagram confirms success, the temporary Supabase objects and local queue files are removed. GitHub Actions commits the queue deletion.

Uploading a file does **not** publish immediately. It waits for the next scheduled run unless you manually run the workflow.

## Required GitHub Actions secrets

Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret | Source |
| --- | --- |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase service-role key |
| `GEMINI_KEY` | Google AI Studio API key |
| `IG_USER_ID` | Instagram professional account ID |
| `INSTA_TOKEN` | Current Instagram/Meta access token with publishing permission |
| `TG_TOKEN` | Optional Telegram bot token |
| `TG_CHAT_ID` | Optional Telegram chat or group ID |

Supabase must contain a **public** Storage bucket named `home-decor`.

Optional repository variable:

| Variable | Default | Purpose |
| --- | --- | --- |
| `GRAPH_API_VERSION` | `v21.0` | Allows the Meta Graph API version to be updated without editing code |

Do not commit API keys or tokens to the repository.

## Naming images

Images are processed in natural filename order. One run publishes one filename group.

| Example | Result |
| --- | --- |
| `candle.jpg` | Single-image post |
| `candle_1.jpg`, `candle_2.jpg`, `candle_3.png` | One three-image carousel |
| `01_candle.jpg`, `02_vase.jpg` | Two separate posts, processed over two runs |

## Safe manual test

1. Upload a test image to `queue/`.
2. Open **Actions → Post to Instagram → Run workflow**.
3. Leave **dry_run** enabled for the first test.

Dry-run mode does not call Supabase, Gemini, Instagram, or Telegram, and does not delete queue files. A real manual post requires turning dry-run off.

## Failure behavior

- Missing secrets produce one clear error listing the missing names.
- Instagram failure preserves the local queue files.
- Temporary Supabase objects are cleaned up after success and after failed publishing attempts.
- Telegram is optional and cannot make a successful Instagram post fail.

## Schedule

The workflow uses timezone-aware schedules, so New Zealand daylight-saving changes are handled automatically:

```yaml
schedule:
  - cron: "0 11 * * *"
    timezone: "Pacific/Auckland"
  - cron: "0 19 * * *"
    timezone: "Pacific/Auckland"
```

## Repository structure

```text
blushcozydecor-ig-autoposter/
├── .github/workflows/post.yml
├── queue/
├── poster.py
├── requirements.txt
└── README.md
```
