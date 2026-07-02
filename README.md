# 🤖 AI-Powered PR Review System

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/orchestration-LangGraph-1c1c1c)](https://github.com/langchain-ai/langgraph)
[![LLM](https://img.shields.io/badge/LLM-Groq%20(free)-orange)](https://console.groq.com)

An agentic code review system that reads a GitHub pull request and gives it a real review - bugs, security issues, code quality, missing tests - using a free Groq-hosted LLM. It runs as a CLI tool you can point at any PR, or as a GitHub Action that comments automatically on every PR opened against your repo.

## Why this exists

Most "AI PR review" scripts are a single prompt wrapped around a diff. This one isn't. The system first **decides how much scrutiny a PR needs** before deciding what to run: a one-line typo fix gets a fast, fixed pipeline, while a PR touching auth, secrets, or hundreds of lines gets routed through an LLM planner that chooses tools dynamically, and can loop back for deeper security analysis if it finds something critical. That distinction - fixed orchestration vs. genuine planning - is the core design goal of this project.

**Where it's useful:**
- Solo developers or small teams who want a second pair of eyes on every PR without paying for a hosted review tool
- Open source maintainers triaging contributions from unfamiliar contributors
- Teaching / portfolio projects that want to demonstrate agentic LLM architecture (planning, conditional routing, decision loops) rather than a simple prompt-chain

---

## Table of Contents

- [How It Works](#how-it-works)
- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [GitHub Actions (Auto-Review)](#github-actions-auto-review)
- [Configuration](#configuration)
- [Example Output](#example-output)
- [Limitations](#limitations)
- [Roadmap](#roadmap)

---

## How It Works

1. **Fetch** — pull PR metadata, changed files, and the raw diff from the GitHub REST API.
2. **Parse** — chunk the diff into LLM-safe pieces, splitting cleanly on file boundaries.
3. **Preprocess** — classify the PR as `simple` or `complex` based on lines changed, file count, and whether security-sensitive files/keywords are touched.
4. **Plan** — route to one of two planners:
   - **Simple Planner**: a fixed, fast tool sequence, no LLM call.
   - **LLM Planner**: asks Groq which tools are worth running given the PR's context.
5. **Execute** — run the planned tools (code review, security analysis, static analysis).
6. **Decide** — a decision node inspects the findings so far. If critical issues were found, it loops back and runs a deeper security pass. If code-quality issues were found early, it can add a static analysis pass. Otherwise it proceeds to summarize. This loop is capped (`max_iterations`) so it always terminates.
7. **Summarize** — aggregate every finding into a single score (1–10) and a verdict: `APPROVE`, `REQUEST_CHANGES`, or `COMMENT`.
8. **Report** — format everything into a polished Markdown report, printed to terminal, saved to file, and/or posted as a GitHub PR comment.

---

## Features

| Category | What it checks |
|---|---|
| 🚨 Critical Issues | Hardcoded secrets, SQL injection patterns, dangerous calls (`eval`, `exec`, `pickle.loads`) |
| 🔒 Security | LLM-driven vulnerability scan per diff chunk (SQL injection, XSS, auth issues, disabled SSL verification) |
| 📝 Code Quality | LLM-driven review for readability, naming, logic issues, and suggestions |
| ⚙️ Static Analysis | Regex-based checks: bare `except:`, leftover debug prints, TODO/FIXME markers, deep nesting, oversized functions |
| 🧪 Test Coverage | Surfaced as part of the aggregated findings |
| 👍 Positive Feedback | The model is also asked to call out things the PR does well |

Other notable behavior:
- **Conditional, looping workflow** — not a fixed sequential pipeline. Built on [LangGraph](https://github.com/langchain-ai/langgraph) with real conditional edges and a bounded decision loop.
- **Dynamic tool selection** — the LLM planner picks tools based on PR risk, not a hardcoded list.
- **Pattern-based pre-checks** — fast regex security checks run before the LLM call, so obvious issues (e.g. a hardcoded API key) are always caught even if the model misses them.
- **Graceful degradation** — if the LLM returns malformed JSON, the relevant tool logs the failure and the workflow continues rather than crashing.
- **LangSmith-traceable** — tool calls go through `ChatGroq` (LangChain's Groq wrapper), so if you set LangSmith env vars, every LLM call in the workflow is automatically traced.

---

## Architecture

![Architecture](assets/architecture.jpeg)

State is carried through every node as a single `ReviewState` dataclass (`src/state.py`), which tracks the PR data, findings collected so far, loop iteration count, and the final score/verdict/report.

---

## Project Structure

```
ai-pr-reviewer/
│
├── main.py                          # CLI entry point
├── config.py                        # Loads & validates .env
├── requirements.txt
├── .env.example
│
├── src/
│   ├── state.py                     # ReviewState — shared state across the graph
│   ├── workflow.py                  # LangGraph graph definition (nodes + edges)
│   ├── github_client.py             # GitHub REST API wrapper
│   ├── reporter.py                  # Formats final review into Markdown
│   │
│   ├── agents/
│   │   ├── preprocessing_agent.py   # Classifies PR as simple/complex
│   │   ├── simple_planner.py        # Fixed tool plan (no LLM call)
│   │   └── llm_planner.py           # Groq-driven dynamic tool plan
│   │
│   └── tools/
│       ├── fetch_pr_tool.py         # Wraps GitHubClient for the graph
│       ├── parse_diff_tool.py       # Chunks the raw diff
│       ├── code_review_tool.py      # LLM code quality review
│       ├── security_analysis_tool.py# Pattern checks + LLM security review
│       ├── static_analysis_tool.py  # Regex-based static checks
│       └── summarizer_tool.py       # Aggregates findings into score/verdict
│
└── .github/
    └── workflows/
        └── pr-review.yml            # GitHub Actions — auto-review on PR open
```

---

## Getting Started

### Prerequisites

- Python 3.11+ (matches the version used in CI; 3.9+ should also work)
- A free [Groq API key](https://console.groq.com) — no credit card required
- A [GitHub Personal Access Token](https://github.com/settings/tokens) — only required for private repos or posting comments

### Installation

```bash
git clone https://github.com/deepanshuiiitv/AI-powered-PR-review-system.git
cd AI-powered-PR-review-system

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Environment Variables

Copy the example file and fill in your keys:

```bash
cp .env.example .env
```

```env
# Required
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional — needed for private repos or --post-comment
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Verify it loaded correctly:

```bash
python -c "from config import Config; c = Config(); print('Key loaded:', c.groq_api_key[:8] + '...')"
```

### Dependencies

Installed via `requirements.txt`:

```
python-dotenv
requests
groq
langgraph
langchain
langchain-core
langchain-community
langsmith
langchain-groq
```

---

## Usage

### Quickstart

```bash
python3 main.py --pr https://github.com/owner/repo/pull/42
```

### Owner / repo / number syntax

```bash
python3 main.py --owner owner --repo repo --number 42
```

### Save the report to a file

```bash
python3 main.py --pr https://github.com/owner/repo/pull/42 --output file
# Saves to: pr_review_owner_repo_42.md
```

### Print and save

```bash
python3 main.py --pr https://github.com/owner/repo/pull/42 --output both
```

### Post the review as a GitHub PR comment

```bash
python3 main.py --pr https://github.com/owner/repo/pull/42 --post-comment
# Requires GITHUB_TOKEN in .env
```

### CLI Reference

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
  --format               markdown | json (default: markdown)
  --post-comment        Post the review as a GitHub PR comment
  --no-color            Disable colored terminal output
```

> **Note:** `--model` and `--format` are accepted by the CLI for forward compatibility but the workflow currently calls Groq with a fixed model (`llama-3.3-70b-versatile`) inside each tool. If you need a different model, update the `ChatGroq(model=...)` calls in `src/tools/code_review_tool.py`, `src/tools/security_analysis_tool.py`, and `src/agents/llm_planner.py`.

---

## GitHub Actions (Auto-Review)

The workflow at `.github/workflows/pr-review.yml` runs the reviewer automatically on every `opened`, `synchronize`, or `reopened` pull request event.

**Setup:**

1. Add `GROQ_API_KEY` as a repository secret: **Settings → Secrets and variables → Actions → New repository secret**.
2. `GITHUB_TOKEN` is provided automatically by GitHub Actions — no setup needed.
3. Open a PR. The bot posts a review comment and uploads the Markdown report as a build artifact.

---

## Configuration

| Variable | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | ✅ | Auth for all LLM calls (planning, code review, security analysis) |
| `GITHUB_TOKEN` | Optional | Needed for private repos and `--post-comment` |

**LLM model:** `llama-3.3-70b-versatile` via Groq, called through `langchain_groq.ChatGroq` in every LLM-backed node (planner, code review, security analysis). Using the LangChain wrapper means calls are automatically traced if you have LangSmith environment variables configured.

**Decision loop bounds:** `ReviewState.max_iterations` (default `3`) caps how many times the `tool_executor` → `decision` loop can run, guaranteeing termination even if findings keep triggering re-analysis.

---

## Example Output

```
======================================================================
 AI-POWERED PR REVIEW SYSTEM 
======================================================================

PR: deepanshuiiitv/AI-powered-PR-review-system#7
URL: https://github.com/deepanshuiiitv/AI-powered-PR-review-system/pull/7

→ Initializing agentic workflow...
→ Starting agent loop...
======================================================================
  [Preprocessing] COMPLEX PR detected
    • Changes: 140 LOC, 3 files
    • Risk level: high
    • Files to focus: testing purpose/auth.py, testing purpose/database.py

  [LLM Planner] Groq decided: security_analysis → code_review → summarizer

→ Tool Execution [Iteration 1]
  Running: security_analysis
    ✓ Analyzed 1 chunk(s)
      - Critical: 2, Security: 1
  Running: code_review
    ✓ Reviewed 1 chunk(s), found 4 issues
  Running: summarizer
    ✓ Score: 3.0/10
    ✓ Verdict: REQUEST_CHANGES

→ Agent Decision: Critical issues found, running deeper security

→ Tool Execution [Iteration 2]
  Running: security_analysis
    ✓ Analyzed 1 chunk(s)

→ Agent Decision: Enough analysis done, moving to summarize

→ Formatting report...
  ✓ Report formatted
======================================================================

#  AI Code Review

##  REQUEST CHANGES

**Quality Score:** 3/10  `###-------`

###  Summary
Found 2 critical issue(s) that must be fixed before merging.

---

##  Critical Issues (2)

### 1. `testing purpose/database.py`
 Issue: SQL query built via string concatenation
 Fix: Use parameterized queries

### 2. `testing purpose/auth.py`
 Issue: Passwords hashed with MD5, hardcoded credential check
 Fix: Use a salted hash (bcrypt/argon2) and remove the hardcoded admin check

 Review complete!
```

---

## Limitations

- **Diff-only context** — the model reviews diff chunks, not the full file or repo, so it can miss issues that only make sense with broader context.
- **LLM JSON parsing isn't bulletproof** — malformed model output is caught and logged as an error rather than crashing the run, but that chunk's findings are lost.
- **Fixed model per tool** — the `--model` CLI flag is accepted but not yet wired through to the LangChain calls.
- **No persistent memory** — every run starts fresh; there's no learning from past reviews on the same repo.
- **Groq free-tier rate limits** apply (see [console.groq.com](https://console.groq.com) for current limits) — large PRs with many chunks will make multiple sequential calls.

## Roadmap

- [ ] Wire `--model` through to all `ChatGroq` calls
- [ ] Add `--format json` output support to the reporter
- [ ] Inline PR review comments (per-line) instead of a single issue comment
- [ ] Configurable decision-loop strategy (currently hardcoded in `node_decision`)
- [ ] Unit tests for the chunking logic in `parse_diff_tool.py` and the scoring logic in `summarizer_tool.py`
- [ ] Optional caching of GitHub API responses for repeat runs on the same PR

---
