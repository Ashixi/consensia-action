# 🤖 Consensia AI Reviewer Action

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Dependency Security](https://img.shields.io/badge/Dependency%20Security-Enabled-brightgreen.svg)](#dependency-guard)

Automated, AI-powered Code Review for your GitHub Commits and Pull Requests. 

Consensia integrates a multi-agent AI system (Security Sentinel, Performance Architect, Clean Code Advocate, Edge-Case Hunter) overseen by **"THE JUDGE"** to analyze your `git diff`. It catches bugs, security vulnerabilities, and performance bottlenecks *before* you merge, leaving detailed inline comments and actionable code suggestions directly on your PR.

---

## 📑 Table of Contents

1. [✨ Features](#features)
2. [⚙️ How It Works](#how-it-works)
3. [🚀 Quick Start Guide](#quick-start-guide)
4. [💻 Usage Scenarios](#usage-scenarios)
   - [Scenario 1: Pull Request Review (Recommended)](#scenario-1-reviewing-pull-requests-recommended)
   - [Scenario 2: Direct Commit Review](#scenario-2-reviewing-direct-commits)
5. [🎛️ Configuration Reference](#configuration-reference)
6. [🌐 The Consensia Ecosystem](#the-consensia-ecosystem)

---

## ✨ Features

* **Autonomous Context:** Consensia is not just a linter. The AI autonomously explores your repository. If a `diff` references a new method, it automatically fetches its implementation from other files to uncover hidden vulnerabilities or logic bugs.
* **Team Styleguide Integration:** Consensia reads your `.consensia.yml`, `.eslintrc`, or `CONTRIBUTING.md` and follows your naming and architecture standards, reducing false positives.
* **Incremental Analysis (Smart Retries):** On PR updates, Consensia remembers previous analysis and focuses on whether previously found bugs are fixed, saving tokens and time.
* **Dependency Guard:** Security Sentinel now audits any changes to `package.json` or `requirements.txt` for suspicious libraries or vulnerable versions.
* **Accurate Inline Comments:** Improved line mapping ensures comments land precisely, minimizing GitHub API errors.
* **Multi-Agent Consensus:** Not just one LLM, but a team of specialized AI agents analyzing your code from different perspectives.
* **Inline Comments & Auto-Suggestions:** Posts feedback directly on the specific lines of code. It can even provide ready-to-commit code suggestions (`suggestion` blocks) for quick fixes.
* **Smart Build Blocking:** Configure the action to automatically fail the CI/CD pipeline (exit code 1) if **CRITICAL** bugs or security vulnerabilities are found.
* **Smart Diff Truncation:** Optimizes token usage by analyzing context cleanly (using `git diff -U1`).
* **Customizable Power:** Choose between `ECONOMY`, `BALANCED`, or `MAX_POWER` modes depending on your needs.
* **Real-time WebSocket Streaming:** Uses WebSocket connections for stable, long-running deep analysis without GitHub Action HTTP timeouts.

---

## ⚙️ How It Works

When a PR is opened or a commit is pushed, Consensia Action extracts the `git diff` and sends it to our multi-agent backend:
1. **The Specialists:** Security, Performance, Clean Code, and Edge-Case agents review the code independently.
2. **Consensus Rounds:** Agents read each other's reports to refine their findings and eliminate false positives.
3. **The Judge:** A final Arbiter aggregates the feedback, formats it into precise inline comments, and determines if the changes contain critical blockers.

---

## 🚀 Quick Start Guide

Follow these simple steps to integrate Consensia into your repository.

### Step 1: Get Your API Key
You need a CLI/API key to use the service.
1. Go to [consensia.world](https://consensia.world).
2. Log in and navigate to your Account Settings.
3. Generate a new **CLI API Key**. *Keep this key safe!*

### Step 2: Add the Key to GitHub Secrets
Your repository needs access to this key securely.
1. Go to your GitHub repository.
2. Click on **Settings** > **Secrets and variables** > **Actions**.
3. Click **New repository secret**.
4. Name it `CONSENSIA_API_KEY` and paste your key into the value field.

### Step 3: Create the Workflow File
You need to tell GitHub Actions when to run Consensia. Choose one of the usage scenarios below and add the `.yml` file to your repository in the `.github/workflows/` folder.

---

## 💻 Usage Scenarios

### Scenario 1: Reviewing Pull Requests (Recommended)
This workflow triggers when a Pull Request is opened or updated. It analyzes the differences and posts a formal Review with inline comments.

Create a file at `.github/workflows/ai-pr-review.yml`:

```yaml
name: Consensia PR Review

on:
  pull_request:
    types: [opened, synchronize, edited]

# IMPORTANT: These permissions are required to post comments on the PR
permissions:
  contents: read
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
          fail-on-critical: 'true' # Automatically block PR if critical bugs are found
```

### Scenario 2: Reviewing Direct Commits
This workflow triggers on direct pushes to specific branches and leaves a general comment on the commit itself.

Create a file at `.github/workflows/ai-commit-review.yml`:

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
---

## 🎛️ Configuration Reference

Here is a detailed list of all the inputs you can pass to the `with:` section of the Action:

| Input | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `api-key` | **Yes** | - | Your Consensia CLI API Key. Pass via `${{ secrets.CONSENSIA_API_KEY }}`. |
| `github-token` | **Yes** | - | Passed as `${{ secrets.GITHUB_TOKEN }}`. Used by the action to interact with the GitHub API to post comments. |
| `target` | **Yes** | - | What to review. Valid options: `pr` (Pull Request) or `commit` (Direct push). |
| `mode` | No | `BALANCED` | AI Analysis depth. Options:<br>• `ECONOMY` (Cheaper, smaller context)<br>• `BALANCED` (Standard approach)<br>• `MAX_POWER` (Deepest analysis, includes deep dependency analysis with Dependency Guard, uses more tokens). |
| `rounds` | No | `2` | Number of internal consensus rounds the AI agents will perform before giving the final verdict. |
| `fail-on-critical` | No | `false` | If set to `true`, the Action will fail (exit code 1) and block the PR if the AI flags any issue as `CRITICAL`. |
| `session-id` | No | - | Session identifier for incremental analysis. For PRs, use `${{ github.event.pull_request.number }}`. |
| `api-url` | No | `https://api.consensia.world/cli/analyze-diff` | Custom API URL. Useful if you are self-hosting the backend or testing. |

---

## 🛡️ Dependency Guard

Any change to your dependencies (`package.json`, `requirements.txt`, etc.) is strictly audited for suspicious libraries or vulnerable versions by the Security Sentinel agent.

---

## 🧩 Example: Custom Rules File

You can easily configure Consensia to follow your team's styleguide. Example `.consensia.yml`:

```yaml
rules:
  use_tabs: false
  prefer_functional_programming: true
```

---

## 🌐 The Consensia Ecosystem

This GitHub Action is just one part of the Consensia platform. Visit [consensia.world](https://consensia.world) to unlock the full potential of AI-driven code reviews:

* **Web-Based Analysis:** Paste code snippets, upload files, or chat with the AI consensus team directly in your browser.
* **Account Dashboard:** Manage your API keys, track your token usage, and review your past analysis sessions.
* **Flexible Billing:** Use your free credits, pay as you go, or upgrade to Consensia Pass for unlimited power using your own API keys.

👉 **[Try the Web App](https://consensia.world)** 👉 **[Consensia Backend Repository](https://github.com/Illya301a/consensia.git)** ---

## 📝 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
