import os
import sys
import json
import requests
import subprocess

def get_pr_diff():
    base_ref = os.environ.get("GITHUB_BASE_REF")
    subprocess.run(["git", "fetch", "origin", base_ref], check=True)
    result = subprocess.run(
        ["git", "diff", f"origin/{base_ref}...HEAD"], 
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()

def main():
    api_key = os.environ.get("CONSENSIA_API_KEY")
    gh_token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("REPO")
    pr_number = os.environ.get("PR_NUMBER")
    commit_sha = os.environ.get("COMMIT_SHA")
    api_url = os.environ.get("API_URL")
    mode = os.environ.get("MODE", "BALANCED")
    rounds = int(os.environ.get("ROUNDS", 2))

    if not all([api_key, gh_token, repo, pr_number, commit_sha]):
        print("Missing required environment variables.")
        sys.exit(1)

    diff_text = get_pr_diff()
    if not diff_text:
        print("No changes found in diff. Skipping review.")
        sys.exit(0)

    print(f"Sending diff ({len(diff_text)} chars) to Consensia API ({mode} mode, {rounds} rounds)...")
    
    response = requests.post(
        api_url,
        json={"diff_text": diff_text, "mode": mode, "scenario": "CODE_REVIEW", "rounds": rounds},
        headers={"x-api-key": api_key, "Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"Consensia API Error: {response.text}")
        sys.exit(1)

    data = response.json()
    verdict = data.get("verdict", {})
    inline_comments = verdict.get("inline_comments", [])
    
    general_summary = f"## 👨‍⚖️ AI Consensia Verdict: {verdict.get('title', 'Review')}\n\n"
    general_summary += verdict.get("summary", "")
    general_summary += f"\n\n*⏱ Tokens used: {data.get('tokens_used', 0)}*"

    gh_api_base = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {gh_token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    valid_inline = []
    unplaced_comments = []

    for c in inline_comments:
        if c.get("path") and c.get("line"):
            icon = "🚨" if c.get("type") == "CRITICAL" else "💡"
            valid_inline.append({
                "path": c.get("path"),
                "line": int(c.get("line")),
                "body": f"{icon} **{c.get('type')}**: {c.get('body')}"
            })
        else:
            unplaced_comments.append(c)

    if unplaced_comments:
        general_summary += "\n\n### General Findings\n"
        for c in unplaced_comments:
            icon = "🚨" if c.get("type") == "CRITICAL" else "💡"
            general_summary += f"- {icon} **{c.get('path', 'General')}**: {c.get('body')}\n"

    payload = {
        "commit_id": commit_sha,
        "event": "COMMENT",
        "body": general_summary,
        "comments": valid_inline
    }

    print("Posting review to GitHub...")
    review_resp = requests.post(gh_api_base, json=payload, headers=headers)
    
    if review_resp.status_code == 422:
        print("GitHub rejected inline comments (likely invalid line numbers). Falling back to general comment.")
        
        fallback_body = general_summary + "\n\n### Detailed Issues:\n"
        for c in valid_inline:
            fallback_body += f"- **{c['path']} (Line {c['line']})**: {c['body']}\n"
            
        fallback_payload = {
            "commit_id": commit_sha,
            "event": "COMMENT",
            "body": fallback_body
        }
        requests.post(gh_api_base, json=fallback_payload, headers=headers)

    elif review_resp.status_code not in [200, 201]:
        print(f"Failed to post PR review: {review_resp.text}")
        sys.exit(1)

    print("Review posted successfully!")

if __name__ == "__main__":
    main()