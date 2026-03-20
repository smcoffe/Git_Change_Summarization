"""Call an OpenAI-compatible API to produce plain-English summaries of git commit batches.

Works with both the hosted OpenAI service and locally-hosted models served via vLLM
(or any other OpenAI-compatible server).  Point ``base_url`` at your vLLM instance,
e.g. ``http://192.168.1.50:8000/v1``, and the same code path is used for both.
"""

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


def summarise(
    api_key: str,
    model: str,
    commits: list[dict],
    base_url: Optional[str] = None,
) -> tuple[str, dict]:
    """Call an OpenAI-compatible chat API and return (summary_string, token_usage_dict).

    Args:
        api_key:  API key for OpenAI.  When using a local vLLM server this can be
                  any non-empty string (e.g. ``"not-needed"``); vLLM ignores it.
        model:    Model name or path as understood by the server.  For vLLM this is
                  typically the Hugging Face model ID used when the server was started,
                  e.g. ``"mistralai/Mistral-7B-Instruct-v0.2"``.
        commits:  List of commit dicts produced by git_parser.
        base_url: Base URL of the OpenAI-compatible endpoint, including the ``/v1``
                  path suffix (e.g. ``"http://192.168.1.50:8000/v1"``).  When
                  ``None`` (the default) the standard OpenAI hosted API is used.

    Returns:
        A tuple of (summary_string, token_usage_dict).
        token_usage_dict keys: prompt_tokens, completion_tokens, total_tokens.
        On error the summary is a fallback string and all token counts are 0.
    """
    if not commits:
        return "No commits to summarise.", dict(_ZERO_USAGE)

    prompt = build_prompt(commits)

    try:
        # Build client kwargs.  base_url routes the client to a local vLLM server
        # (or any other OpenAI-compatible endpoint) instead of api.openai.com.
        client_kwargs: dict = {"api_key": api_key or "not-needed"}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = openai.OpenAI(**client_kwargs)
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
        print(f"[llm_client] ERROR: API call failed: {exc}", file=sys.stderr)
        return "Summary unavailable — API error.", dict(_ZERO_USAGE)
    except Exception as exc:
        print(f"[llm_client] ERROR: Unexpected error during summarisation: {exc}", file=sys.stderr)
        return "Summary unavailable — API error.", dict(_ZERO_USAGE)
