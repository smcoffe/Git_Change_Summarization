# Git Intel

Git Intel is a local tool that monitors one or more git repositories, uses an OpenAI language model to turn recent commit history into plain-English summaries, stores those summaries in a running JSON log, and serves a clean browser dashboard showing a live file tree and scrollable change timeline for every tracked repository.

---

## Setup

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Configure**

   Open `config.json` and fill in your details:

   - Replace `"sk-YOUR-KEY-HERE"` with your [OpenAI API key](https://platform.openai.com/api-keys).
   - Replace the placeholder entry in `"repositories"` with the actual name and **absolute path** of each local git repository you want to track.
   - Adjust `schedule_minutes`, `lookback_commits`, and other settings as desired.

   > ⚠️ Never commit `config.json` (with a real API key) to version control.

---

## Running

### Start the monitor

```bash
python main.py
```

Git Intel will print a startup summary, immediately process all configured repos, write summaries to `store/`, and — if `schedule_minutes > 0` — continue polling on the configured interval. Press **Ctrl+C** to stop.

### Serve the dashboard

Open a second terminal in the `git-intel/` root directory and run:

```bash
python -m http.server 5500
```

Then open your browser to:

```
http://localhost:5500/dashboard/
```

The dashboard reads from the `store/` directory, which is accessible at the server root, so the two terminal sessions can run simultaneously.

---

## Config reference

| Key | Type | Description |
|---|---|---|
| `openai_api_key` | string | Your OpenAI API key. |
| `model` | string | OpenAI chat model to use (e.g. `gpt-4o-mini`, `gpt-4o`, `gpt-3.5-turbo`). |
| `repositories` | array | List of repos to monitor. Each entry needs `"name"` (display label) and `"path"` (absolute path on disk). |
| `schedule_minutes` | integer | How often to check for new commits, in minutes. Set to `0` to run once and exit. |
| `lookback_commits` | integer | Max number of recent commits to process on the very first run per repo. |
| `dashboard_port` | integer | Informational — the port shown in the startup message. Pass this to `http.server` manually. |

---

## Dashboard

### Opening it

Serve from the `git-intel/` root with `python -m http.server 5500`, then visit `http://localhost:5500/dashboard/`.

### Panels

| Panel | Description |
|---|---|
| **Repository selector** (top of sidebar) | Switch between tracked repositories. |
| **File Tree** (sidebar) | The current working tree of the selected repo at the time of the last `main.py` run. Folders are shown with `▸`, files with `·`. |
| **Change Timeline** (main area) | Plain-English summaries of commit batches in reverse-chronological order. Each entry shows the date/time, a prose summary, and stat badges for files changed, insertions, and deletions. |
| **↻ Sync button** | Re-fetches the latest data from `store/` without reloading the page. |
| **Last updated** (footer) | Timestamp of the most recent dashboard refresh. |

---

## Security note

Your OpenAI API key is stored in `config.json` in plain text. Add `config.json` to your `.gitignore` before committing this project anywhere, or use a separate secrets manager.
