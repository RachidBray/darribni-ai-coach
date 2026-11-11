#!/usr/bin/env python3
"""Sanitize an n8n workflow export before committing it to this public repo.

Usage:
    python3 scripts/sanitize_n8n_export.py <input.json> [<output.json>]

If no output path is given, the input file is rewritten in place.

What it does:
- drops instance-specific fields (workflow id, versionId, pinData, staticData, webhookId, ...)
- replaces every credential reference with YOUR_CREDENTIAL_ID
- replaces sub-workflow IDs with SELECT_<WORKFLOW_NAME> placeholders
- replaces Google Calendar IDs with YOUR_..._CALENDAR_ID placeholders
- fails loudly if anything that still looks like a secret is left behind
"""
import json
import re
import sys

DROP_TOP_LEVEL = {"id", "versionId", "activeVersionId", "pinData", "staticData", "triggerCount",
                  "createdAt", "updatedAt", "shared", "tags", "active", "isArchived",
                  "parentFolderId", "scopes", "activeVersion", "description"}
DROP_NODE_FIELDS = {"webhookId", "credentials"}

CREDENTIALS_BY_TYPE = {
    "n8n-nodes-base.telegram": ("telegramApi", "Telegram account"),
    "n8n-nodes-base.telegramTrigger": ("telegramApi", "Telegram account"),
    "n8n-nodes-base.postgres": ("postgres", "Postgres account"),
    "n8n-nodes-base.googleCalendar": ("googleCalendarOAuth2Api", "Google Calendar account"),
    "n8n-nodes-base.strava": ("stravaOAuth2Api", "Strava account"),
    "n8n-nodes-base.stravaTrigger": ("stravaOAuth2Api", "Strava account"),
    "@n8n/n8n-nodes-langchain.lmChatOpenRouter": ("openRouterApi", "OpenRouter account"),
}

CALENDAR_ID = re.compile(r"[0-9a-f]{32,}@group\.calendar\.google\.com")

# Patterns that must never end up in the repo.
SECRET_PATTERNS = {
    "Google Calendar ID": CALENDAR_ID,
    "Telegram bot token": re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    "OpenRouter / OpenAI key": re.compile(r"\bsk-(?:or-)?[A-Za-z0-9_-]{20,}"),
    "Anthropic key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "Postgres URL with password": re.compile(r"postgres(?:ql)?://[^:\s]+:[^@\s]+@"),
    "Private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


def placeholder_for_workflow(name: str) -> str:
    slug = re.sub(r"[^A-Z0-9]+", "_", (name or "WORKFLOW").upper()).strip("_")
    return f"SELECT_{slug}"


def calendar_placeholder(value: str, node_name: str) -> str:
    if "Delete" in node_name or "Sync" in node_name or "Create" in node_name:
        return "YOUR_DARRIBNI_CALENDAR_ID@group.calendar.google.com"
    return "YOUR_PLAN_CALENDAR_ID@group.calendar.google.com"


def scrub_strings(obj, node_name):
    if isinstance(obj, str):
        return CALENDAR_ID.sub(lambda m: calendar_placeholder(m.group(0), node_name), obj)
    if isinstance(obj, list):
        return [scrub_strings(v, node_name) for v in obj]
    if isinstance(obj, dict):
        return {k: scrub_strings(v, node_name) for k, v in obj.items()}
    return obj


def sanitize(wf: dict) -> dict:
    out = {k: v for k, v in wf.items() if k not in DROP_TOP_LEVEL}
    settings = dict(out.get("settings") or {})
    settings.pop("availableInMCP", None)
    out["settings"] = settings or {"executionOrder": "v1"}
    out["meta"] = {"templateCredsSetupCompleted": True}

    nodes = []
    for node in wf.get("nodes", []):
        n = {k: v for k, v in node.items() if k not in DROP_NODE_FIELDS}
        params = n.get("parameters", {})

        wid = params.get("workflowId")
        if isinstance(wid, dict) and wid.get("__rl"):
            name = wid.get("cachedResultName", "")
            params["workflowId"] = {"__rl": True, "value": placeholder_for_workflow(name),
                                    "mode": "list", "cachedResultName": name}

        n["parameters"] = scrub_strings(params, n.get("name", ""))

        cred = CREDENTIALS_BY_TYPE.get(n.get("type"))
        if cred:
            n["credentials"] = {cred[0]: {"id": "YOUR_CREDENTIAL_ID", "name": cred[1]}}
        nodes.append(n)
    out["nodes"] = nodes
    return out


def find_leaks(text: str):
    return [label for label, rx in SECRET_PATTERNS.items() if rx.search(text)]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else src
    with open(src, encoding="utf-8") as f:
        wf = json.load(f)
    clean = sanitize(wf)
    text = json.dumps(clean, indent=2, ensure_ascii=False)
    leaks = find_leaks(text)
    if leaks:
        print(f"REFUSING to write {dst}: still looks like it contains {', '.join(leaks)}", file=sys.stderr)
        sys.exit(2)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"sanitized -> {dst}")


if __name__ == "__main__":
    main()
