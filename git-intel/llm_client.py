"""Call the OpenAI API to produce plain-English summaries of git commit batches."""

import sys
from typing import Optional

import openai

# Sentinel token_usage dict returned when no API call is made or the call fails.
_ZERO_USAGE: dict = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def build_prompt(commits: list[dict]) -> str:
    """Format a list of commit dicts into a clean prompt string for the LLM."""
    lines = [
        "You are a software-change summariser. Below is a list of git commits.",
        "Write a plain-English paragraph (3–5 sentences) that describes what changed across these commits.",
        "Avoid technical jargon where possible. Mention which files or areas of the codebase were affected.",
        "Do NOT reproduce raw commit SHAs or raw diff output.",
        "",
        "Commits:",
    ]
    for i, commit in enumerate(commits, start=1):
        stats = commit.get("stats", {})
        changed = ", ".join(commit.get("changed_files", [])[:10])
        if len(commit.get("changed_files", [])) > 10:
            changed += f" … and {len(commit['changed_files']) - 10} more"
        lines.append(
            f"{i}. [{commit.get('timestamp', '')}] {commit.get('author', 'unknown')}: "
            f"{commit.get('message', '').splitlines()[0]}"
        )
        lines.append(
            f"   Files changed: {stats.get('files', 0)}, "
            f"+{stats.get('insertions', 0)} / -{stats.get('deletions', 0)}"
        )
        if changed:
            lines.append(f"   Affected files: {changed}")
    lines.append("")
    lines.append("Summary:")
    return "\n".join(lines)


def _extract_usage(response) -> dict:
    """Extract token counts from an OpenAI response object into a plain dict."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return dict(_ZERO_USAGE)
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }


def summarise(api_key: str, model: str, commits: list[dict]) -> tuple[str, dict]:
    """Call the OpenAI chat API and return (summary_string, token_usage_dict).

    token_usage_dict keys: prompt_tokens, completion_tokens, total_tokens.
    On error the summary is a fallback string and all token counts are 0.
    """
    if not commits:
        return "No commits to summarise.", dict(_ZERO_USAGE)

    prompt = build_prompt(commits)

    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise technical writer who explains software changes "
                        "to a non-technical audience. Use clear, plain language."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=400,
        )
        summary = response.choices[0].message.content.strip()
        token_usage = _extract_usage(response)
        return summary, token_usage
    except openai.OpenAIError as exc:
        print(f"[llm_client] ERROR: OpenAI API call failed: {exc}", file=sys.stderr)
        return "Summary unavailable — API error.", dict(_ZERO_USAGE)
    except Exception as exc:
        print(f"[llm_client] ERROR: Unexpected error during summarisation: {exc}", file=sys.stderr)
        return "Summary unavailable — API error.", dict(_ZERO_USAGE)
