import os
import sys
import json
import requests
import subprocess
import asyncio
import websockets
from urllib.parse import urlparse

def get_diff(target_type):
    if target_type == "pr":
        base_ref = os.environ.get("GITHUB_BASE_REF")
        if not base_ref:
            print("Error: GITHUB_BASE_REF is missing for PR target.")
            sys.exit(1)
        subprocess.run(["git", "fetch", "origin", base_ref], check=True)
        result = subprocess.run(
            ["git", "diff", f"origin/{base_ref}...HEAD"], 
            capture_output=True, text=True, check=True
        )
    elif target_type == "commit":
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD~1", "HEAD"], 
                capture_output=True, text=True, check=True
            )
        except subprocess.CalledProcessError:
            EMPTY_TREE_HASH = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
            result = subprocess.run(
                ["git", "diff", EMPTY_TREE_HASH, "HEAD"], 
                capture_output=True, text=True, check=True
            )
    else:
        print(f"Error: Unknown target type '{target_type}'. Use 'pr' or 'commit'.")
        sys.exit(1)
        
    return result.stdout.strip()

async def analyze_via_websocket(ws_url, api_key, diff_text, mode, rounds):
    print(f"Connecting to WebSocket: {ws_url}")
    
    async with websockets.connect(ws_url) as websocket:
        init_data = {
            "token": api_key, 
            "mode": mode,
            "scenario": "CODE_REVIEW",
            "code": diff_text,
            "rounds": rounds
        }
        await websocket.send(json.dumps(init_data))

        final_verdict = None
        tokens_used = 0

        while True:
            try:
                response_str = await websocket.recv()
                event = json.loads(response_str)
                event_type = event.get("type")

                if event_type == "ping":
                    continue 
                elif event_type == "system":
                    print(f"🖥️ System: {event.get('msg')}")
                elif event_type == "state_update":
                    status = event.get("data", {}).get("session_status", "processing")
                elif event_type == "agent_usage":
                    usage = event.get("usage", {})
                    agent = event.get("agent", "Agent")
                    agent_tokens = usage.get('prompt', 0) + usage.get('completion', 0)
                    
                    # ПЛЮСУЄМО токени від кожного агента
                    tokens_used += agent_tokens
                    
                    print(f"🤖 {agent} finished (Tokens: {agent_tokens})")
                elif event_type == "final_verdict":
                    final_verdict = event.get("content")
                    break
                elif event_type == "error":
                    print(f"❌ API Error: {event.get('msg') or event.get('content')}")
                    sys.exit(1)

            except websockets.exceptions.ConnectionClosed as e:
                print(f"❌ WebSocket connection closed unexpectedly: {e}")
                sys.exit(1)

        return final_verdict, tokens_used

def main():
    api_key = os.environ.get("CONSENSIA_API_KEY")
    gh_token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("REPO")
    commit_sha = os.environ.get("COMMIT_SHA")
    target = os.environ.get("TARGET", "").lower()
    pr_number = os.environ.get("PR_NUMBER")
    
    api_url = os.environ.get("API_URL", "https://api.consensia.world/cli/analyze-diff")
    mode = os.environ.get("MODE", "BALANCED")
    rounds = int(os.environ.get("ROUNDS", 2))

    if not all([api_key, gh_token, repo, commit_sha, target]):
        print("Missing required environment variables.")
        sys.exit(1)

    if target == "pr" and not pr_number:
        print("Error: Target is 'pr', but PR_NUMBER is missing.")
        sys.exit(1)

    try:
        diff_text = get_diff(target)
    except subprocess.CalledProcessError as e:
        print(f"Failed to get git diff: {e}")
        sys.exit(1)

    if not diff_text:
        print("No changes found in diff. Skipping review.")
        sys.exit(0)

    print(f"Sending diff ({len(diff_text)} chars) to Consensia API ({mode} mode, {rounds} rounds)...")
    
    parsed = urlparse(api_url)
    ws_scheme = "wss" if parsed.scheme == "https" else "ws"
    ws_url = f"{ws_scheme}://{parsed.netloc}/ws/cli/analyze-diff"

    verdict, tokens_used = asyncio.run(analyze_via_websocket(ws_url, api_key, diff_text, mode, rounds))
    
    if not verdict:
        print("Failed to get final verdict from WebSocket.")
        sys.exit(1)

    inline_comments = verdict.get("inline_comments", [])
    
    general_summary = f"## 👨‍⚖️ AI Consensia Verdict: {verdict.get('title', 'Review')}\n\n"
    general_summary += verdict.get("summary", "")
    general_summary += f"\n\n*⏱ Tokens used: {tokens_used}*\n*ℹ️ 1 Consensia credit = 1000 tokens*"

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

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {gh_token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    print("Posting review to GitHub...")

    if target == "pr":
        gh_api_base = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
        payload = {
            "commit_id": commit_sha,
            "event": "COMMENT",
            "body": general_summary,
            "comments": valid_inline
        }
        review_resp = requests.post(gh_api_base, json=payload, headers=headers)
        
        if review_resp.status_code == 422:
            print("GitHub rejected inline comments. Falling back to general comment.")
            fallback_body = general_summary + "\n\n### Detailed Issues:\n"
            for c in valid_inline:
                fallback_body += f"- **{c['path']} (Line {c['line']})**: {c['body']}\n"
            fallback_payload = {
                "commit_id": commit_sha,
                "event": "COMMENT",
                "body": fallback_body
            }
            review_resp = requests.post(gh_api_base, json=fallback_payload, headers=headers)
            
    elif target == "commit":
        gh_api_base = f"https://api.github.com/repos/{repo}/commits/{commit_sha}/comments"
        fallback_body = general_summary + "\n\n### Detailed Issues:\n"
        if valid_inline:
            for c in valid_inline:
                fallback_body += f"- **{c['path']} (Line {c['line']})**: {c['body']}\n"
        else:
            fallback_body += "No specific line issues found.\n"
            
        payload = {"body": fallback_body}
        review_resp = requests.post(gh_api_base, json=payload, headers=headers)

    if review_resp.status_code not in [200, 201]:
        print(f"Failed to post review: {review_resp.text}")
        sys.exit(1)

    print("Review posted successfully!")

if __name__ == "__main__":
    main()
