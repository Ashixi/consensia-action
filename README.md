# 🤖 Consensia AI Reviewer Action

Automated, AI-powered Code Review for your GitHub Commits and Pull Requests. 

Consensia integrates a multi-agent AI system (Security Sentinel, Performance Architect, Clean Code Advocate, Edge-Case Hunter) overseen by "THE JUDGE" to analyze your `git diff`. It catches bugs, security vulnerabilities, and performance bottlenecks *before* you merge, leaving detailed inline comments directly on your code.

## ✨ Features
* **Multi-Agent Consensus:** Not just one LLM, but a team of specialized AI agents analyzing your code from different perspectives.
* **Inline Comments:** Posts feedback directly on the specific lines of code in your Pull Request.
* **Customizable Power:** Choose between `ECONOMY`, `BALANCED`, or `MAX_POWER` modes depending on your needs.
* **Real-time WebSocket Streaming:** Uses WebSocket connections for stable, long-running deep analysis without GitHub Action timeouts.

## 🚀 Prerequisites

1. **Consensia API Key:** You need a CLI/API key from [consensia.world](https://consensia.world).
2. **GitHub Secrets:** Add your Consensia API key to your repository secrets as `CONSENSIA_API_KEY` (Settings > Secrets and variables > Actions > New repository secret).

## 🛠️ Usage

### Scenario 1: Reviewing Pull Requests (Recommended)
This workflow triggers when a Pull Request is opened or updated. It analyzes the differences and posts a formal Review with inline comments.

Create a file in your repository: `.github/workflows/ai-pr-review.yml`

```yaml
name: Consensia PR Review

on:
  pull_request:
    types: [opened, synchronize]

# IMPORTANT: These permissions are required to post comments on the PR
permissions:
  contents: write
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0 # Required to accurately compare PR branches

      - name: Run Consensia AI Reviewer
        uses: Ashixi/consensia-action@main
        with:
          api-key: ${{ secrets.CONSENSIA_API_KEY }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
          target: 'pr'
          mode: 'BALANCED'
          rounds: '2'
```
### Scenario 2: Reviewing Direct Commits
This workflow triggers on direct pushes to specific branches and leaves a comment on the commit itself.

Create a file in your repository: `.github/workflows/ai-commit-review.yml`

```yaml
name: Consensia Commit Review

on:
  push:
    branches:
      - main

permissions:
  contents: write # Required to post comments on commits

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          fetch-depth: 2 # Required to compare HEAD with HEAD~1

      - name: Run Consensia AI Reviewer
        uses: Ashixi/consensia-action@main
        with:
          api-key: ${{ secrets.CONSENSIA_API_KEY }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
          target: 'commit'
          mode: 'ECONOMY'
```
## ⚙️ Inputs Configuration

| Input | Required | Default | Description |
| --- | --- | --- | --- |
| `api-key` | **Yes** | - | Your Consensia CLI API Key. Pass via secrets. |
| `github-token` | **Yes** | - | `${{ secrets.GITHUB_TOKEN }}`. Used by the action to post comments. |
| `target` | **Yes** | - | What to review. Valid options: `pr` (Pull Request) or `commit` (Direct push). |
| `mode` | No | `BALANCED` | AI Analysis depth. Options: `ECONOMY`, `BALANCED`, `MAX_POWER`. |
| `rounds` | No | `2` | Number of consensus rounds the AI agents will perform. |
| `api-url` | No | `https://api.consensia.world/cli/analyze-diff` | Custom API URL (for self-hosting or testing). |
```
```
## 🌐 Discover the Consensia Ecosystem

This GitHub Action is just one part of the Consensia platform. Visit [consensia.world](https://consensia.world) to unlock the full potential of AI-driven code reviews:

* **Web-Based Analysis:** Paste code snippets, upload files, or chat with the AI consensus team directly in your browser.
* **Account Dashboard:** Manage your API keys, track your token usage, and review your past analysis sessions.
* **Flexible Billing:** Use your free credits or upgrade to Consensia Pass for unlimited power.
```
```
👉 **[Try the Web App](https://consensia.world)**
👉 **[Consensia repo](https://consensia.world)**

## 📝 License
This project is licensed under the MIT License.
```
