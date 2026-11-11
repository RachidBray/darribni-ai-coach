#!/usr/bin/env python3
"""Scan files for secrets and private IDs before they get committed.

Usage:
    python3 scripts/check_secrets.py            # scan staged files (pre-commit)
    python3 scripts/check_secrets.py --all      # scan every tracked file
    python3 scripts/check_secrets.py FILE...    # scan specific files

Exit code 1 if anything suspicious is found.
"""
import re
import subprocess
import sys

PATTERNS = {
    "Google Calendar ID": r"[0-9a-f]{32,}@group\.calendar\.google\.com",
    "Telegram bot token": r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b",
    "OpenRouter / OpenAI key": r"\bsk-(?:or-)?[A-Za-z0-9_-]{20,}",
    "Anthropic key": r"\bsk-ant-[A-Za-z0-9_-]{20,}",
    "Google API key": r"\bAIza[0-9A-Za-z_-]{35}\b",
    "GitHub token": r"\bgh[pousr]_[A-Za-z0-9]{36,}\b",
    "AWS access key": r"\bAKIA[0-9A-Z]{16}\b",
    "Postgres URL with password": r"postgres(?:ql)?://[^:\s/]+:[^@\s]+@",
    "Private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "n8n API key (JWT)": r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b",
    "Real n8n credential id": r'"credentials"\s*:\s*\{[^}]*"id"\s*:\s*"(?!YOUR_CREDENTIAL_ID)[A-Za-z0-9]{8,}"',
}
BLOCKED_FILENAMES = re.compile(r"(^|/)(\.env(\..*)?|.*\.pem|.*\.key|credentials\.json|.*\.ics)$")
ALLOWED_FILENAMES = re.compile(r"(^|/)\.env\.example$")
COMPILED = {k: re.compile(v) for k, v in PATTERNS.items()}
PLACEHOLDER = re.compile(r"replace-me|YOUR_|example", re.I)


def git_files(args):
    out = subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout
    return [f for f in out.splitlines() if f]


def main():
    argv = sys.argv[1:]
    if argv == ["--all"]:
        files = git_files(["ls-files"])
    elif argv:
        files = argv
    else:
        files = git_files(["diff", "--cached", "--name-only", "--diff-filter=ACM"])

    problems = []
    for path in files:
        if BLOCKED_FILENAMES.search(path) and not ALLOWED_FILENAMES.search(path):
            problems.append(f"{path}: this kind of file must never be committed")
            continue
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except (FileNotFoundError, IsADirectoryError):
            continue
        for label, rx in COMPILED.items():
            for m in rx.finditer(text):
                if PLACEHOLDER.search(m.group(0)):
                    continue
                line = text.count("\n", 0, m.start()) + 1
                problems.append(f"{path}:{line}: possible {label}")

    if problems:
        print("Secret scan FAILED:\n  " + "\n  ".join(problems), file=sys.stderr)
        print("\nRemove the value, use a placeholder, or run scripts/sanitize_n8n_export.py.", file=sys.stderr)
        sys.exit(1)
    print(f"Secret scan passed ({len(files)} files).")


if __name__ == "__main__":
    main()
