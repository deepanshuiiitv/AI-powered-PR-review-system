# 🤖 AI-Powered PR Review System

> **Zero cost. Zero setup friction. Real AI feedback on every pull request.**
>
> Uses [Groq](https://console.groq.com) (free LLM API) + [GitHub REST API](https://docs.github.com/en/rest) (free).
> No credit card. No paid tier. No rate-limit worries for normal usage.

---

## Table of Contents

- [What It Does](#what-it-does)
- [Architecture](#architecture)
- [File Structure](#file-structure)
- [File-by-File Explanation](#file-by-file-explanation)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [CLI Reference](#cli-reference)
- [GitHub Actions (Auto-review)](#github-actions-auto-review)
- [Free API Limits](#free-api-limits)
- [Troubleshooting](#troubleshooting)
- [How the AI Review Works](#how-the-ai-review-works)
- [Sample Output](#sample-output)

---

## What It Does

You give it a GitHub PR URL. It gives you back a detailed AI code review covering:

| Category | What It Checks |
|---|---|
| 🚨 Critical Issues | Bugs, logic errors, null pointer risks, off-by-one |
| 🔒 Security | SQL injection, hardcoded secrets, insecure auth, input validation |
| ⚡ Performance | N+1 queries, blocking I/O, unnecessary loops, memory leaks |
| 💡 Code Quality | Readability, naming, complexity, dead code, DRY violations |
| 🧪 Test Coverage | Missing tests, weak assertions, untested edge cases |
| 📌 Best Practices | SOLID principles, error handling, logging, documentation |

It gives each PR a **score out of 10** and a verdict: `APPROVE`, `REQUEST_CHANGES`, or `COMMENT`.

---

## Architecture

```
Developer
                            │
                   python main.py --pr URL
                            │
                    ┌───────▼────────┐
                    │   main.py      │  ← CLI entry point
                    │  (orchestrator)│
                    └───────┬────────┘
                            │ loads
                    ┌───────▼────────┐
                    │   config.py    │  ← reads .env file
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
                    │github_client.py│  ← step 1: fetch
                    │ • get PR meta  │
                    │ • get files    │
                    │ • get raw diff │
                    └───────┬────────┘
                            │ HTTPS request
                    ┌───────▼────────┐
                    │  GitHub API    │  ← free, no cost
                    │  (REST v3)     │
                    └───────┬────────┘
                            │ diff + files + metadata
                    ┌───────▼────────┐
                    │  pr_parser.py  │  ← step 2: process
                    │ • filter files │
                    │ • chunk diff   │
                    │ • build context│
                    └───────┬────────┘
                            │ structured dict
                    ┌───────▼────────┐
                    │ ai_reviewer.py │  ← step 3: review
                    │ • build prompt │
                    │ • call Groq    │
                    │ • retry on 429 │
                    │ • merge chunks │
                    └───────┬────────┘
                            │ HTTPS request
                    ┌───────▼────────┐
                    │  Groq API      │  ← free, llama-3.3-70b
                    └───────┬────────┘
                            │ JSON review
                    ┌───────▼────────┐
                    │  reporter.py   │  ← step 4: format
                    └──┬──────────┬──┘
                       │          │
                  Terminal      .md file
                  (stdout)   pr_review_*.md
                                  │
                        (optional) GitHub PR comment
                        via --post-comment flag
```

### Data Flow Summary

1. **CLI** parses the PR URL and extracts `owner`, `repo`, `number`
2. **GitHubClient** fetches PR metadata, file list, and raw unified diff via GitHub REST API
3. **PRParser** filters out auto-generated/lock files, splits large diffs into token-safe chunks, and assembles a structured dict
4. **AIReviewer** sends each chunk to Groq with a detailed system prompt, handles rate limits with exponential backoff, and merges multi-chunk results
5. **Reporter** formats the JSON review into a polished Markdown report with score bars, verdict badges, and a stats table
6. Output goes to terminal, a `.md` file, or back to GitHub as a PR comment

---

## File Structure

```
ai-pr-reviewer/
│
├── main.py                  # CLI entry point — run this
├── config.py                # Loads .env, validates required keys
├── requirements.txt         # Only 2 dependencies
├── .env.example             # Template — copy to .env and fill in
├── .gitignore
│
├── src/
│   ├── __init__.py
│   ├── github_client.py     # All GitHub REST API calls
│   ├── pr_parser.py         # Diff parsing, chunking, file filtering
│   ├── ai_reviewer.py       # Groq API integration + review logic
│   └── reporter.py          # Formats JSON review into Markdown
│
└── .github/
    └── workflows/
        └── pr-review.yml    # GitHub Actions — auto-review on PR open
```

---

## File-by-File Explanation

### `main.py` — Orchestrator & CLI

The entry point. Uses Python's `argparse` to build a user-friendly CLI.

**Responsibilities:**
- Accepts `--pr URL` or `--owner / --repo / --number` flags
- Parses the GitHub PR URL to extract owner, repo, and PR number
- Calls each module in sequence: GitHub → Parser → AI → Reporter
- Routes output to terminal, file, or GitHub comment based on flags
- Prints colored status updates as each step completes

**Key functions:**
- `parse_pr_url(url)` — splits a GitHub URL into its parts
- `main()` — top-level orchestration; the only function that calls all others

---

### `config.py` — Configuration Loader

Loads environment variables from your `.env` file using `python-dotenv`.

**Responsibilities:**
- Reads `GROQ_API_KEY` and `GITHUB_TOKEN` from `.env`
- Raises a clear error if the required Groq key is missing
- GitHub token is optional (only needed for private repos or `--post-comment`)

```python
# What it does internally:
load_dotenv()                        # reads .env into os.environ
self.groq_api_key = os.getenv(...)   # pulls the key
if not self.groq_api_key: raise ...  # gives a helpful error message
```

---

### `src/github_client.py` — GitHub API Client

Handles all communication with the [GitHub REST API v3](https://docs.github.com/en/rest).

**Responsibilities:**
- Fetches PR metadata (title, author, branch names, labels, draft status)
- Fetches the list of changed files with per-file stats
- Fetches the raw unified diff (the actual code changes)
- Posts a comment back to the PR (when `--post-comment` is used)
- Paginates file lists automatically (handles PRs with 100+ files)

**Endpoints used:**
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/repos/{owner}/{repo}/pulls/{number}` | PR metadata |
| GET | `/repos/{owner}/{repo}/pulls/{number}/files` | Changed files |
| GET | `/repos/{owner}/{repo}/pulls/{number}` (diff header) | Raw diff |
| POST | `/repos/{owner}/{repo}/issues/{number}/comments` | Post review |

**Authentication:** Adds `Authorization: Bearer TOKEN` header when `GITHUB_TOKEN` is set. Public repos work without any token.

---

### `src/pr_parser.py` — Diff Parser & Chunker

Transforms raw GitHub API responses into a clean, structured dict ready for the AI.

**Responsibilities:**
- **Filters out noise:** skips lock files (`package-lock.json`, `yarn.lock`, `poetry.lock`), minified files (`.min.js`), source maps (`.map`), and other auto-generated content
- **Chunks large diffs:** splits diffs larger than 12,000 characters into smaller pieces that fit within the LLM's token limit. Always breaks on file boundaries (`diff --git` lines) so each chunk contains complete files
- **Builds context header:** assembles a summary of PR title, author, branch, description, and file stats that gets sent with every AI call

**Key constants:**
```python
CHUNK_SIZE = 12_000      # characters per chunk (~3k tokens safety margin)
REVIEWABLE_EXTENSIONS    # set of file types worth reviewing
SKIP_PATTERNS            # regex for lock/generated files to skip
```

---

### `src/ai_reviewer.py` — AI Review Engine

The core intelligence of the system. Sends the PR to Groq's free LLM API and gets back a structured JSON review.

**Responsibilities:**
- Constructs a detailed system prompt defining the review dimensions
- Sends each diff chunk to Groq with the full PR context header
- Handles rate limiting with automatic retry (waits 30s on HTTP 429)
- Safely parses JSON responses (handles accidental markdown fences)
- Merges multi-chunk reviews into a single coherent result using a pessimistic merge strategy for verdicts (if any chunk says `REQUEST_CHANGES`, the final verdict is `REQUEST_CHANGES`)

**System prompt covers:**
1. Code quality (readability, naming, complexity)
2. Correctness (bugs, edge cases, logic errors)
3. Security (injection, secrets, auth bypass)
4. Performance (N+1, blocking I/O, memory)
5. Best practices (SOLID, DRY, error handling)
6. Tests (missing coverage, weak assertions)
7. Documentation (missing docstrings, misleading comments)

**Groq model used:** `llama-3.3-70b-versatile` (default)
- Context window: 128k tokens
- Speed: ~400 tokens/second
- Cost: **free**

**Response format:** Forces JSON output via `response_format: {"type": "json_object"}` so the response is always parseable.

---

### `src/reporter.py` — Output Formatter

Takes the raw AI review dict and formats it into a polished, human-readable Markdown document.

**Responsibilities:**
- Renders a verdict badge (`🟢 APPROVE`, `🔴 REQUEST CHANGES`, `🟡 COMMENT`)
- Renders a visual score bar using block characters (`████████░░`)
- Sections: Summary → Critical Issues → Security → Improvements → Missing Tests → Positives → Recommendations → Stats table
- Caps improvement suggestions at 15 to keep the report readable
- Embeds a link back to the original PR

**Output example:**
```markdown
# 🤖 AI Code Review

## 🔴 REQUEST CHANGES

**Quality Score:** 6/10  `██████░░░░`

### 📋 Summary
The PR fixes the bug but introduces a SQL injection risk...

### 🚨 Critical Issues (1)
### 1. `auth.py`
❗ Issue: Raw string formatting in SQL query
✅ Fix: Use parameterized queries
```

---

### `.github/workflows/pr-review.yml` — GitHub Actions

Runs the reviewer automatically whenever a PR is opened, updated, or reopened in your repository.

**Trigger:** `pull_request` events (`opened`, `synchronize`, `reopened`)

**Steps:**
1. Check out the repo
2. Set up Python 3.11
3. Install the two dependencies
4. Run `main.py` with `--post-comment` to post the review as a GitHub comment
5. Upload the `.md` review file as a build artifact

**Required secrets** (add in repo Settings → Secrets → Actions):
- `GROQ_API_KEY` — your free Groq key
- `GITHUB_TOKEN` — automatically provided by GitHub Actions (no setup needed)

---

## Prerequisites

- Python 3.8 or higher
- A free [Groq API key](https://console.groq.com) (takes 1 minute, no credit card)
- A [GitHub Personal Access Token](https://github.com/settings/tokens) (only needed for private repos or posting comments)

---

## Installation

```bash
# 1. Get the code
git clone https://github.com/YOUR_USERNAME/ai-pr-reviewer.git
cd ai-pr-reviewer

# 2. Create a virtual environment (recommended)
python3 -m venv venv

# 3. Activate it
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows

# 4. Install dependencies
pip install -r requirements.txt

# 5. Set up environment variables
cp .env.example .env
# Now edit .env and add your keys (see Configuration below)
```

---

## Configuration

Open your `.env` file and fill in your keys:

```env
# Required — get free at https://console.groq.com
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional — needed for private repos or --post-comment
# Get at https://github.com/settings/tokens
# Scopes: repo (private) or public_repo + write:discussion (comments)
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Verify your setup:**
```bash
python -c "from config import Config; c = Config(); print('✅ Key loaded:', c.groq_api_key[:8] + '...')"
```

---

## Usage

### Quickstart

```bash
# Simplest — just paste any GitHub PR URL
python main.py --pr https://github.com/owner/repo/pull/42
```

### Review your own PR

```bash
python main.py --pr https://github.com/deepanshuiiitv/AI-powered-PR-review-system/pull/1
```

### Save to file

```bash
python main.py --pr https://github.com/owner/repo/pull/42 --output file
# Saves to: pr_review_owner_repo_42.md
```

### Post review as GitHub comment

```bash
python main.py --pr https://github.com/owner/repo/pull/42 --post-comment
# Requires GITHUB_TOKEN in .env
```

### Print AND save

```bash
python main.py --pr https://github.com/owner/repo/pull/42 --output both
```

### Use a different Groq model

```bash
# Larger context window (good for big PRs)
python main.py --pr https://github.com/owner/repo/pull/42 --model mixtral-8x7b-32768

# Faster, lighter model
python main.py --pr https://github.com/owner/repo/pull/42 --model llama-3.1-8b-instant
```

### Output raw JSON

```bash
python main.py --pr https://github.com/owner/repo/pull/42 --format json
```

### Without a full URL

```bash
python main.py --owner facebook --repo react --number 123
```

---

## CLI Reference

```
usage: main.py [-h] (--pr URL | --owner OWNER) [--repo REPO] [--number N]
               [--model MODEL] [--output {terminal,file,both}]
               [--format {markdown,json}] [--post-comment] [--no-color]

Options:
  --pr URL              Full GitHub PR URL (simplest option)
  --owner OWNER         GitHub repo owner (use with --repo & --number)
  --repo REPO           GitHub repo name
  --number N            PR number
  --model MODEL         Groq model to use (default: llama-3.3-70b-versatile)
  --output              terminal | file | both (default: terminal)
  --format              markdown | json (default: markdown)
  --post-comment        Post the review as a GitHub PR comment
  --no-color            Disable colored terminal output
```

---

## GitHub Actions (Auto-review)

To automatically get AI reviews on every PR in your repo:

**Step 1:** Copy `.github/workflows/pr-review.yml` into your repository.

**Step 2:** Add your Groq key as a repository secret:
- Go to your repo → **Settings** → **Secrets and variables** → **Actions**
- Click **New repository secret**
- Name: `GROQ_API_KEY`, Value: your key starting with `gsk_`

> `GITHUB_TOKEN` is automatically provided by GitHub Actions — you don't need to add it.

**Step 3:** Open any pull request. The bot will post a review comment automatically within ~30 seconds.

---

## Free API Limits

### Groq (LLM)
| Limit | Value |
|---|---|
| Requests per day | 14,400 |
| Requests per minute | 30 |
| Tokens per minute | 6,000 (llama-3.3-70b) |
| Cost | **$0** |

For a team of 5 developers opening 10 PRs/day, that's well within the free tier.

### GitHub API
| Limit | Value |
|---|---|
| Unauthenticated | 60 requests/hour |
| Authenticated (free token) | 5,000 requests/hour |
| Cost | **$0** |

This tool makes 3 API calls per review. You can review ~1,600 PRs/hour with a free token.

---

## Troubleshooting

### `❌ GitHub API error: 404 Not Found`
- Make sure your URL has **no `.git`** at the end
  - ❌ `https://github.com/user/repo.git/pull/1`
  - ✅ `https://github.com/user/repo/pull/1`
- For private repos, ensure `GITHUB_TOKEN` is set in `.env`

### `❌ Groq API error: 401 Unauthorized`
- Your `GROQ_API_KEY` is missing or wrong in `.env`
- Run `cat .env` to verify the key is there
- Ensure there are no spaces around the `=` sign

### `error: externally-managed-environment`
- Don't install packages into the system Python. Use a virtual environment:
  ```bash
  python3 -m venv venv && source venv/bin/activate
  pip install -r requirements.txt
  ```

### `ModuleNotFoundError: No module named 'dotenv'`
- Your virtual environment isn't activated. Run: `source venv/bin/activate`

### AI returns an unparseable response
- This is rare. The tool will fall back gracefully and show a partial review.
- Try a different model: `--model llama-3.1-8b-instant`

### Very large PRs (1000+ line diffs)
- The tool auto-chunks large diffs and reviews each part separately
- It takes a bit longer but works correctly
- Consider using `--model mixtral-8x7b-32768` for its larger context window

---

## How the AI Review Works

The system sends this information to the AI for each review:

```
PR TITLE:    Fix SQL injection in login endpoint
AUTHOR:      devuser
BRANCH:      fix/sql-injection → main
LABELS:      security, bug

DESCRIPTION:
Replaces string concatenation in SQL queries with parameterized queries.

STATS: 3 files reviewed  +47 / -12 lines

FILES CHANGED:
  [modified ] src/auth.py    (+35/-10)
  [modified ] tests/test_auth.py  (+12/-2)
  [unchanged] README.md

DIFF:
[full unified diff here]
```

The AI is instructed to return structured JSON with all review categories. The system prompt defines exact scoring rubrics and verdict criteria to ensure consistent, actionable output.

---

## Sample Output

```
── Fetching PR data from GitHub ...
   Repo  : deepanshuiiitv/AI-powered-PR-review-system
   PR #  : 1

   Title : Add initial project structure
   Author: deepanshuiiitv
   Files : 6 changed

── Running AI review with llama-3.3-70b-versatile ...
   Sending diff to Groq...

════════════════════════════════════════════════════
# 🤖 AI Code Review

> Generated: 2026-05-10 10:30 UTC
> PR: Add initial project structure

---

## 🟡 COMMENT

**Quality Score:** 7/10  `███████░░░`

### 📋 Summary
The project structure is well-organised with clear separation of concerns.
The GitHub client and parser modules are clean. Consider adding error
handling for network timeouts and input validation on the PR URL parser.

---

## 💡 Suggested Improvements (3)

- **`src/ai_reviewer.py`** — No timeout on requests.post
  → Add `timeout=60` to prevent indefinite hangs

- **`src/github_client.py`** — No retry on 5xx server errors
  → Wrap _get() with a retry decorator for transient failures

- **`main.py`** — PR number not validated as positive integer
  → Add: `if number <= 0: raise ValueError`

---

## 🧪 Missing Test Coverage (2)

- Unit tests for PRParser.chunk_diff with diff > CHUNK_SIZE
- Test for Reporter.format when review has empty critical_issues

---

## 👍 Positive Aspects

- Clear module boundaries — each file has a single responsibility
- Graceful fallback in _safe_parse() for malformed JSON responses
- Auto-pagination in get_pr_files() handles large PRs correctly

---

## 📌 General Recommendations

- Add a --dry-run flag to preview what will be sent to the API
- Consider caching GitHub responses to speed up re-runs on the same PR

---

## 📊 PR Statistics

| Metric         | Value |
|----------------|-------|
| Files changed  | 6     |
| Files reviewed | 6     |
| Lines added    | +312  |
| Lines removed  | -0    |

════════════════════════════════════════════════════

  🟡 Verdict : COMMENT
  📊 Score   : 7/10

✨ Review complete!
```