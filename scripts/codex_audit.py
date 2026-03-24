"""Pre-commit audit: sends staged diffs to GPT-4o for SOLID/DRY/KISS review."""

import os
import subprocess
import sys

SYSTEM_PROMPT = """\
You are a Senior Software Architect performing a code review.

Analyze the git diff provided and check for:
1. SOLID principle violations
2. DRY violations (duplicated logic)
3. KISS violations (unnecessary complexity)
4. Security issues (OWASP top 10)
5. Obvious bugs or race conditions

Respond in this exact format:

CRITICAL: <count>
WARNINGS: <count>

Then list each issue as:
- [CRITICAL|WARNING] <file>:<line> — <description>

If there are no issues, respond with:
CRITICAL: 0
WARNINGS: 0

No issues found. Code looks good.
"""


def get_staged_diff() -> str:
    result = subprocess.run(
        ["git", "diff", "--cached", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def audit_diff(diff: str) -> tuple[bool, str]:
    """Send diff to GPT-4o and return (passed, response_text)."""
    try:
        from openai import OpenAI
    except ImportError:
        print("WARNING: openai package not installed — skipping audit.")
        return True, ""

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("WARNING: OPENAI_API_KEY not set — skipping audit.")
        return True, ""

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Review this diff:\n\n{diff}"},
        ],
        max_tokens=2048,
    )

    text = response.choices[0].message.content or ""
    # Parse critical count from response
    for line in text.splitlines():
        if line.startswith("CRITICAL:"):
            count = int(line.split(":")[1].strip())
            return count == 0, text

    # If we can't parse, pass by default
    return True, text


def main() -> int:
    diff = get_staged_diff()
    if not diff.strip():
        print("No staged changes to audit.")
        return 0

    print("Running AI code audit on staged changes...")
    passed, report = audit_diff(diff)
    if report:
        print(report)

    if not passed:
        print("\nCOMMIT BLOCKED: Critical issues found. Fix them before committing.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
