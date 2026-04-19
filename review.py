import os
import sys
import json
import requests
import subprocess
import asyncio
import websockets
import yaml
from urllib.parse import urlparse

def load_config():
    """Зчитує конфігураційний файл .consensia.yml з кореня репозиторію."""
    config = {}
    if os.path.isfile(".consensia.yml"):
        try:
            with open(".consensia.yml", "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
                print("✅ Знайдено конфігураційний файл .consensia.yml.")
        except Exception as e:
            print(f"⚠️ Помилка завантаження .consensia.yml: {e}")
    else:
        print("ℹ️ Файл .consensia.yml не знайдено. Використовуються стандартні налаштування.")
    return config

def get_repo_file_tree(ignore_paths=None):
    """Отримує дерево файлів репозиторію, ігноруючи вказані шляхи."""
    try:
        result = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
        files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if ignore_paths:
            # Базова фільтрація для ignore_paths
            files = [f for f in files if not any(ip.replace('**', '') in f for ip in ignore_paths)]
        return files
    except subprocess.CalledProcessError as e:
        print(f"Failed to get file tree: {e}")
        return []

def get_user_context(target_type, repo, pr_number, commit_sha, gh_token):
    """Отримує контекст (заголовок/тіло PR або повідомлення коміту)."""
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {gh_token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    context_text = ""
    try:
        if target_type == "pr" and pr_number:
            url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                context_text = f"PR Title: {data.get('title', '')}\nPR Body: {data.get('body', '')}"
        elif target_type == "commit" and commit_sha:
            url = f"https://api.github.com/repos/{repo}/commits/{commit_sha}"
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                context_text = f"Commit Message: {data.get('commit', {}).get('message', '')}"
    except Exception as e:
        print(f"Failed to fetch context: {e}")
    return context_text

def get_diff(target_type):
    """Отримує git diff для поточного PR або коміту."""
    if target_type == "pr":
        base_ref = os.environ.get("GITHUB_BASE_REF")
        if not base_ref:
            # Запасний варіант, якщо base_ref відсутній (наприклад, під час issue_comment)
            try:
                return subprocess.run(["git", "diff", "-U1", "HEAD~1", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
            except subprocess.CalledProcessError:
                return ""
        subprocess.run(["git", "fetch", "origin", base_ref], check=True)
        result = subprocess.run(
            ["git", "diff", "-U1", f"origin/{base_ref}...HEAD"], 
            capture_output=True, text=True, check=True
        )
    else:
        try:
            result = subprocess.run(["git", "diff", "-U1", "HEAD~1", "HEAD"], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError:
            EMPTY_TREE_HASH = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
            result = subprocess.run(["git", "diff", "-U1", EMPTY_TREE_HASH, "HEAD"], capture_output=True, text=True, check=True)
    return result.stdout.strip()

async def analyze_via_websocket(ws_url, payload):
    """Встановлює WebSocket з'єднання та спілкується з бекендом."""
    print(f"Connecting to WebSocket: {ws_url}")
    async with websockets.connect(ws_url) as websocket:
        await websocket.send(json.dumps(payload))
        final_result = None
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
                elif event_type == "request_files":
                    requested_files = event.get("files", [])
                    print(f"📂 AI requested full files: {requested_files}")
                    documents = []
                    for filepath in requested_files:
                        if ".." not in filepath and os.path.isfile(filepath):
                            try:
                                with open(filepath, "r", encoding="utf-8") as f:
                                    documents.append({"name": filepath, "content": f.read()})
                            except Exception as e:
                                print(f"⚠️ Could not read {filepath}: {e}")
                    await websocket.send(json.dumps({"type": "provide_files", "documents": documents}))
                elif event_type == "agent_usage":
                    usage = event.get("usage", {})
                    tokens_used += usage.get('prompt', 0) + usage.get('completion', 0)
                elif event_type == "final_verdict":
                    final_result = event.get("content")
                    break
                elif event_type == "error":
                    print(f"❌ API Error: {event.get('msg') or event.get('content')}")
                    sys.exit(1)
            except websockets.exceptions.ConnectionClosed as e:
                print(f"❌ WebSocket closed unexpectedly: {e}")
                sys.exit(1)

        return final_result, tokens_used

def apply_auto_fix(fixes, repo, pr_number, gh_token):
    """Застосовує виправлення від AI та пушить їх у гілку."""
    if not fixes:
        print("Немає виправлень для застосування.")
        return

    print("🚀 Застосування Auto-Fixes...")
    for fix in fixes:
        filepath = fix.get('path')
        new_code = fix.get('new_content')
        if filepath and new_code:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_code)
                subprocess.run(["git", "add", filepath], check=True)
                print(f"Оновлено файл: {filepath}")
            except Exception as e:
                print(f"Помилка при оновленні файлу {filepath}: {e}")
    
    try:
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"])
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"])
        subprocess.run(["git", "commit", "-m", "🤖 Consensia Auto-Fix applied"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("✅ Auto-fixes успішно відправлені (pushed).")
        
        # Додаємо коментар у PR про успішний автофікс
        if repo and pr_number:
            url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
            headers = {"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"}
            requests.post(url, json={"body": "✅ **Consensia Auto-Fix** успішно застосовано та додано у гілку!"}, headers=headers)
        
    except subprocess.CalledProcessError as e:
        print(f"Failed to commit fixes: {e}")

def main():
    api_key = os.environ.get("CONSENSIA_API_KEY")
    gh_token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("REPO")
    target = os.environ.get("TARGET", "").lower()
    pr_number = os.environ.get("PR_NUMBER")
    api_url = os.environ.get("API_URL", "https://api.consensia.world/cli/analyze-diff")
    mode = os.environ.get("MODE", "BALANCED")
    rounds = int(os.environ.get("ROUNDS", 2))
    fail_on_critical = os.environ.get("FAIL_ON_CRITICAL", "false").lower() == "true"
    
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")

    # Парсимо конфіг
    config = load_config()
    consensia_config = config.get("consensia", {})
    ignore_paths = consensia_config.get("ignore_paths", [])
    
    parsed = urlparse(api_url)
    ws_scheme = "wss" if parsed.scheme == "https" else "ws"
    ws_url = f"{ws_scheme}://{parsed.netloc}/ws/cli/analyze-diff"

    # --- 1. ОБРОБКА КОМАНД (EXPLAIN, AUTO_FIX) ---
    scenario = "CODE_REVIEW"
    comment_body = ""
    fix_targets = []
    
    if event_name == "issue_comment" and os.path.exists(event_path):
        with open(event_path, "r") as f:
            event_data = json.load(f)
            comment_body = event_data.get("comment", {}).get("body", "").strip()
            
        if comment_body.startswith("/consensia explain"):
            scenario = "EXPLAIN"
            comment_body = comment_body.replace("/consensia explain", "").strip()
        elif comment_body.startswith("/consensia fix"):
            scenario = "AUTO_FIX"
            targets_str = comment_body.replace("/consensia fix", "").strip()
            fix_targets = [int(t.strip()) for t in targets_str.split(",") if t.strip().isdigit()]

    if scenario in ["EXPLAIN", "AUTO_FIX"] and not comment_body and not fix_targets:
        print("Порожня команда. Завершення роботи.")
        sys.exit(0)

    # --- 2. ПІДГОТОВКА ДАНИХ ---
    try:
        diff_text = get_diff("pr" if target == "pr" or pr_number else "commit")
    except Exception as e:
        print(f"Failed to get diff: {e}")
        diff_text = ""

    if not diff_text and scenario == "CODE_REVIEW":
        print("Не знайдено змін у diff. Пропускаємо перевірку.")
        sys.exit(0)

    context_text = get_user_context(target, repo, pr_number, os.environ.get("COMMIT_SHA"), gh_token)
    if scenario == "EXPLAIN":
        context_text += f"\n\nUSER QUESTION: {comment_body}"

    file_tree = get_repo_file_tree(ignore_paths)

    # Формуємо payload
    payload = {
        "token": api_key,
        "scenario": scenario,
        "mode": mode,
        "code": diff_text,
        "context": context_text,
        "file_tree": file_tree,
        "rounds": rounds,
        "session_id": pr_number,  # Smart Retries прив'язуються до номеру PR
        "config": consensia_config,
        "fix_targets": fix_targets
    }

    # --- 3. ЗАПУСК АНАЛІЗУ ---
    print(f"Відправка запиту до Consensia API ({scenario} режим)...")
    verdict, tokens_used = asyncio.run(analyze_via_websocket(ws_url, payload))
    
    if not verdict:
        print("Не вдалося отримати відповідь від WebSocket.")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"}

    # --- 4. ОБРОБКА ВІДПОВІДІ ЗАЛЕЖНО ВІД СЦЕНАРІЮ ---
    if scenario == "EXPLAIN":
        comment = f"## 🤖 Consensia Explanation\n\n{verdict.get('explanation', verdict.get('summary', ''))}"
        requests.post(f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments", json={"body": comment}, headers=headers)
        sys.exit(0)
        
    elif scenario == "AUTO_FIX":
        if consensia_config.get("enable_auto_fix", True):
            apply_auto_fix(verdict.get("fixes", []), repo, pr_number, gh_token)
        else:
            print("Auto-fix вимкнено у .consensia.yml (enable_auto_fix: false)")
            requests.post(f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments", json={"body": "⚠️ Функція Auto-Fix наразі вимкнена в `.consensia.yml`."}, headers=headers)
        sys.exit(0)

    # --- 5. ЗВИЧАЙНИЙ CODE REVIEW ---
    inline_comments = verdict.get("inline_comments", [])
    general_summary = f"## 👨‍⚖️ AI Consensia Verdict: {verdict.get('title', 'Review')}\n\n{verdict.get('summary', '')}\n\n*⏱ Tokens used: {tokens_used}*\n*ℹ️ 1 Consensia credit = 1000 tokens*"

    valid_inline = []
    unplaced = []
    has_critical = False

    for c in inline_comments:
        if c.get("type") == "CRITICAL": 
            has_critical = True
            
        if c.get("path") and c.get("line"):
            icon = "🚨" if c.get("type") == "CRITICAL" else "💡"
            body_text = f"{icon} **{c.get('type')}**: {c.get('body')}"
            if c.get("suggestion"): 
                body_text += f"\n\n```suggestion\n{c.get('suggestion')}\n```"
            valid_inline.append({
                "path": c.get("path"), 
                "line": int(c.get("line")), 
                "body": body_text
            })
        else:
            unplaced.append(c)

    if unplaced:
        general_summary += "\n\n### Загальні зауваження (General Findings)\n"
        for c in unplaced:
            icon = "🚨" if c.get("type") == "CRITICAL" else "💡"
            general_summary += f"- {icon} **{c.get('path', 'General')}**: {c.get('body')}\n"

    print("Публікація рев'ю на GitHub...")

    if target == "pr":
        gh_api_base = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
        payload_review = {
            "commit_id": os.environ.get("COMMIT_SHA"),
            "event": "COMMENT",
            "body": general_summary,
            "comments": valid_inline
        }
        review_resp = requests.post(gh_api_base, json=payload_review, headers=headers)
        
        if review_resp.status_code == 422: 
            print("GitHub відхилив inline-коментарі (можливо, рядки поза diff). Використовуємо звичайний коментар.")
            fb_body = general_summary + "\n\n### Детальні зауваження:\n"
            for c in valid_inline: 
                fb_body += f"- **{c['path']} (Line {c['line']})**: {c['body']}\n"
            requests.post(gh_api_base, json={"commit_id": os.environ.get("COMMIT_SHA"), "event": "COMMENT", "body": fb_body}, headers=headers)
            
    elif target == "commit":
        gh_api_base = f"https://api.github.com/repos/{repo}/commits/{os.environ.get('COMMIT_SHA')}/comments"
        fb_body = general_summary + "\n\n### Детальні зауваження:\n"
        if valid_inline:
            for c in valid_inline:
                fb_body += f"- **{c['path']} (Line {c['line']})**: {c['body']}\n"
        else:
            fb_body += "Не знайдено специфічних проблем по рядках.\n"
            
        requests.post(gh_api_base, json={"body": fb_body}, headers=headers)

    print("Рев'ю успішно опубліковано!")
            
    if has_critical and fail_on_critical:
        print("🚨 Знайдено КРИТИЧНІ помилки. Зупиняємо білд (FAIL_ON_CRITICAL=true).")
        sys.exit(1)

if __name__ == "__main__":
    main()