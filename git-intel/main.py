"""Entry point for Git Intel — monitors repos, summarises commits, and serves a dashboard."""

import json
import sys
import time
from pathlib import Path

import schedule

import git_parser
import llm_client
import log_writer

_CONFIG_PATH = Path(__file__).parent / "config.json"

_REQUIRED_KEYS = [
    "openai_api_key",
    "model",
    "repositories",
    "schedule_minutes",
    "lookback_commits",
    "dashboard_port",
]


def load_config() -> dict:
    """Load and validate config.json, exiting with a helpful message on errors."""
    if not _CONFIG_PATH.exists():
        print(f"ERROR: config.json not found at '{_CONFIG_PATH}'. "
              "Copy the template and fill in your values.", file=sys.stderr)
        sys.exit(1)

    try:
        with _CONFIG_PATH.open("r", encoding="utf-8") as fh:
            config = json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"ERROR: config.json is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    missing = [k for k in _REQUIRED_KEYS if k not in config]
    if missing:
        print(
            f"ERROR: config.json is missing required keys: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    if not isinstance(config["repositories"], list) or not config["repositories"]:
        print("ERROR: config.json 'repositories' must be a non-empty list.", file=sys.stderr)
        sys.exit(1)

    for repo in config["repositories"]:
        if "name" not in repo or "path" not in repo:
            print(
                "ERROR: Each entry in 'repositories' must have 'name' and 'path' keys.",
                file=sys.stderr,
            )
            sys.exit(1)

    return config


def run_once(config: dict) -> None:
    """Process all configured repositories: update trees, detect new commits, write summaries."""
    api_key: str = config["openai_api_key"]
    model: str = config["model"]
    lookback: int = int(config["lookback_commits"])
    repos: list[dict] = config["repositories"]

    repo_names = [r["name"] for r in repos]

    for repo in repos:
        name: str = repo["name"]
        path: str = repo["path"]

        # --- 1. Snapshot the file tree ---
        tree = git_parser.get_file_tree(path)
        log_writer.write_file_tree(name, tree)

        # --- 2. Get unprocessed commits ---
        last_sha = log_writer.get_last_sha(name)
        commits = git_parser.get_commits(path, last_sha, lookback)

        # --- 3. Summarise and persist ---
        if commits:
            summary, token_usage = llm_client.summarise(api_key, model, commits)
            entry = log_writer.make_entry(summary, commits, token_usage)
            log_writer.append_entry(name, entry)
            log_writer.append_token_log(name, model, token_usage)
            tok = token_usage
            print(
                f"[{name}] {len(commits)} new commit(s) → summary written. "
                f"Tokens used: {tok['prompt_tokens']} prompt + "
                f"{tok['completion_tokens']} completion = "
                f"{tok['total_tokens']} total"
            )
        else:
            print(f"[{name}] No new commits.")

    # --- 4. Write the dashboard manifest ---
    log_writer.write_index(repo_names)

    # --- 5. Print cumulative token summary ---
    summary = log_writer.get_token_summary()
    overall = summary["overall"]
    if overall["api_calls"] > 0:
        print(
            f"  ↳ Cumulative token usage: "
            f"{overall['total_tokens']} tokens across "
            f"{overall['api_calls']} API call(s) "
            f"(see store/token_usage.json for full log)"
        )


def main() -> None:
    """Load config, print startup info, and run the monitoring loop."""
    config = load_config()

    repos = config["repositories"]
    model = config["model"]
    interval = int(config["schedule_minutes"])
    port = int(config["dashboard_port"])

    print("=" * 60)
    print("  Git Intel — Commit Summariser")
    print("=" * 60)
    print(f"  Model        : {model}")
    print(f"  Repos        : {', '.join(r['name'] for r in repos)}")
    if interval > 0:
        print(f"  Schedule     : every {interval} minute(s)")
    else:
        print("  Schedule     : run once and exit")
    print(f"  Dashboard    : http://localhost:{port}/dashboard/")
    print("=" * 60)

    if interval > 0:
        # Run immediately, then schedule
        run_once(config)
        schedule.every(interval).minutes.do(run_once, config)
        print(f"Scheduler running. Next run in {interval} minute(s). Press Ctrl+C to stop.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down.")
    else:
        run_once(config)
        print("Done.")


if __name__ == "__main__":
    main()
