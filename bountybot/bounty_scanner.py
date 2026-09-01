"""
GitHub Bounty Hunter — Scans GitHub for bounty-worthy issues and opportunities.
Uses GitHub API to discover, evaluate, and track coding jobs.
"""
import os, json, math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin
import requests

from config import load_config, load_state, save_state, get_state_dir


class GitHubBountyHunter:
    """Discovers and evaluates GitHub bounties, issues, and coding jobs."""

    def __init__(self, config=None):
        self.config = config or load_config()
        self.github_token = self.config["github"].get("token", "")
        self.org = self.config["github"]["org"]
        self.base_url = "https://api.github.com"
        self.state = load_state("bounty_jobs")

        # Ensure state structure
        if "jobs" not in self.state:
            self.state["jobs"] = []
        if "stats" not in self.state:
            self.state["stats"] = {"scans": 0, "total_jobs": 0, "last_scan": None}

    def _headers(self):
        headers = {"Accept": "application/vnd.github+json"}
        if self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"
            headers["X-GitHub-Api-Version"] = "2022-11-28"
        return headers

    def _get(self, url, params=None):
        """Make a GET request to GitHub API."""
        try:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 401:
                print(f"  ERROR: GitHub auth failed (token invalid or expired)")
                return None
            elif resp.status_code == 403:
                print(f"  WARNING: GitHub API rate limited. Sleeping and retrying...")
                import time
                time.sleep(60)
                resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
                if resp.status_code == 200:
                    return resp.json()
                print(f"  ERROR: Still rate limited after retry: {resp.status_code}")
                return None
            else:
                print(f"  ERROR: GitHub API {url} -> {resp.status_code}")
                return None
        except requests.exceptions.Timeout:
            print(f"  ERROR: Request timeout for {url}")
            return None
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")
            return None

    def scan_repos(self, search_query: str = "", max_results: int = 50) -> list:
        """Scan GitHub for issues and bounties matching the query."""
        if not self.github_token:
            print("  No GitHub token configured. Skipping bounty scan.")
            return []

        jobs = []
        search_q = search_query or self._build_search_query()

        # Search for issues (not PRs) with labels suggesting bounties
        params = {
            "q": f"{search_q} is:issue is:open",
            "per_page": 100,
            "sort": "comments",
            "order": "desc",
        }

        results = self._get(f"{self.base_url}/search/issues", params)
        if not results:
            return jobs

        total = results.get("total_count", 0)
        items = results.get("items", [])[:max_results]

        print(f"  Found {total} matching issues, evaluating top {len(items)}...")

        for item in items:
            job = self._evaluate_issue(item)
            if job and job["score"] > 0:
                jobs.append(job)

        # Sort by score (highest first)
        jobs.sort(key=lambda x: x["score"], reverse=True)
        return jobs

    def _build_search_query(self) -> str:
        """Build a search query for bounty-worthy issues."""
        skills = self.config["bounty"].get("skills", [])
        skill_queries = [f"+{s}" for s in skills[:5]]  # top 5 skills
        return f'+"{self.config["bounty"].get("min_reward_threshold", 500)}" repo:{self.org}*' + "".join(skill_queries)

    def _evaluate_issue(self, issue: dict) -> Optional[dict]:
        """Evaluate a GitHub issue as a potential bounty/job."""
        title = issue.get("title", "")
        body = (issue.get("body") or "")[:2000]
        repo_name = issue.get("repository_url", "").split("/")[-1]
        labels = [l["name"] if isinstance(l, dict) else l for l in issue.get("labels", [])]
        comments = issue.get("comments", 0)
        created = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
        updated = datetime.fromisoformat(issue["updated_at"].replace("Z", "+00:00"))

        # Extract reward from title/body
        reward = self._extract_reward(title + " " + body)

        # Score the job
        score = 0
        reasons = []

        # Reward factor (0-40)
        if reward >= 3000:
            score += 40
            reasons.append("High reward ($3k+)")
        elif reward >= 1000:
            score += 30
            reasons.append("Good reward ($1k+)")
        elif reward >= 500:
            score += 20
            reasons.append("Moderate reward ($500+)")
        elif reward > 0:
            score += 10
            reasons.append("Low reward")
        else:
            score += 5  # Unknown reward, still might be worth it

        # Skill match (0-25)
        skills = self.config["bounty"].get("skills", [])
        text = (title + " " + body).lower()
        matched_skills = [s for s in skills if s.lower() in text]
        skill_score = min(len(matched_skills) * 5, 25)
        score += skill_score
        if matched_skills:
            reasons.append(f"Skill match: {', '.join(matched_skills[:3])}")

        # Label scoring (0-15)
        bounty_labels = ["bounty", "reward", "paid", "hacktoberfest", "good-first-issue",
                         "up-for-grabs", "starter", "mentorship", "beginner-friendly"]
        matched_labels = [l for l in labels if l.lower() in bounty_labels]
        label_score = min(len(matched_labels) * 5, 15)
        score += label_score
        if matched_labels:
            reasons.append(f"Labels: {', '.join(matched_labels[:3])}")

        # Engagement scoring (0-10)
        if comments > 10:
            score += 10
            reasons.append(f"High engagement ({comments} comments)")
        elif comments > 3:
            score += 5
            reasons.append(f"Moderate engagement ({comments} comments)")

        # Freshness scoring (0-10)
        days_old = (datetime.utcnow() - updated).days
        if days_old < 7:
            score += 10
            reasons.append("Recently active")
        elif days_old < 30:
            score += 5
            reasons.append("Recently updated")

        # Difficulty assessment
        difficulty = self._assess_difficulty(title, body, labels)

        return {
            "id": issue["id"],
            "number": issue["number"],
            "title": title,
            "repo": repo_name,
            "url": issue["html_url"],
            "reward": reward,
            "score": score,
            "difficulty": difficulty,
            "skill_match": matched_skills,
            "matched_labels": matched_labels,
            "comments": comments,
            "days_old": days_old,
            "reasons": reasons,
            "state": issue.get("state", "open"),
            "created_at": issue["created_at"],
            "updated_at": issue["updated_at"],
            "body_preview": body[:300],
            "assigned": issue.get("assignee", {}).get("login", "none") if issue.get("assignee") else "none",
        }

    def _extract_reward(self, text: str) -> float:
        """Extract dollar amount from text."""
        import re
        # Patterns: $1000, 1000 USD, "$1,000", etc.
        patterns = [
            r'\$(\d{1,3}(?:,\d{3})*|\d+)',       # $1000 or $1,000
            r'(\d{1,3}(?:,\d{3})*|\d+)\s*USD',   # 1000 USD
            r'(\d{1,3}(?:,\d{3})*|\d+)\s*\b',    # bare number context
        ]
        amounts = []
        for pat in patterns[:2]:  # First two are most specific
            matches = re.findall(pat, text)
            for m in matches:
                amount = int(m.replace(",", ""))
                if 100 <= amount <= 50000:  # Reasonable bounty range
                    amounts.append(amount)
        return max(amounts) if amounts else 0

    def _assess_difficulty(self, title: str, body: str, labels: list) -> str:
        """Assess job difficulty from title, body, and labels."""
        text = (title + " " + body).lower()
        hard_words = ["complex", "architecture", "system", "distributed", "kernel", "compiler", "security"]
        easy_words = ["tutorial", "simple", "basic", "beginner", "starter", "hello-world"]

        hard = sum(1 for w in hard_words if w in text)
        easy = sum(1 for w in easy_words if w in text)

        label_names = [l.lower() if isinstance(l, str) else l for l in labels]
        if "good-first-issue" in label_names or "starter" in label_names:
            easy += 3

        if easy > hard + 2:
            return "easy"
        elif hard > easy + 1:
            return "hard"
        else:
            return "medium"

    def scan(self) -> list:
        """Run a full bounty scan. Returns list of evaluated jobs."""
        print("\n=== GitHub Bounty Hunter ===")

        if not self.github_token:
            print("  ERROR: No GitHub token configured. Cannot scan.")
            return []

        # Scan with broad query for known bounty sources
        jobs = []

        # 1. Scan own org repos
        print("\n[1/3] Scanning sparkbountybot repos...")
        own_jobs = self._scan_org(self.org)
        jobs.extend(own_jobs)
        print(f"  Found {len(own_jobs)} potential jobs")

        # 2. Scan popular open-source repos for bounty-type issues
        print("\n[2/3] Scanning popular repos for bounty issues...")
        popular = [
            "torvalds/linux", "microsoft/vscode", "facebook/react",
            "tensorflow/tensorflow", "pytorch/pytorch", "python/cpython",
        ]
        for repo in popular[:3]:  # Limit to avoid rate limiting
            print(f"  Scanning {repo}...")
            repo_jobs = self._scan_repo_bounties(repo)
            jobs.extend(repo_jobs)
            print(f"    +{len(repo_jobs)} jobs")

        # 3. Scan for specific bounty labels across GitHub
        print("\n[3/3] Scanning for bounty-labeled issues...")
        bounty_jobs = self._scan_bounty_labels()
        jobs.extend(bounty_jobs)
        print(f"  Found {len(bounty_jobs)} bounty-labeled issues")

        # Deduplicate by title
        seen = set()
        unique_jobs = []
        for job in jobs:
            key = f"{job['repo']}:{job['number']}:{job['title'][:50]}"
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)

        # Sort by score
        unique_jobs.sort(key=lambda x: x["score"], reverse=True)

        # Update state
        self.state["jobs"] = unique_jobs[:self.config["bounty"].get("max_jobs_per_scan", 50)]
        self.state["stats"]["scans"] = self.state["stats"].get("scans", 0) + 1
        self.state["stats"]["last_scan"] = datetime.utcnow().isoformat()
        self.state["stats"]["total_jobs"] = len(unique_jobs)
        save_state("bounty_jobs", self.state)

        # Summary
        rewards = [j["reward"] for j in unique_jobs if j["reward"] > 0]
        total_potential = sum(rewards)
        high_value = [j for j in unique_jobs if j["score"] >= 30]

        print(f"\n=== Scan Complete ===")
        print(f"  Total jobs found: {len(unique_jobs)}")
        print(f"  High-value jobs (score>=30): {len(high_value)}")
        print(f"  Potential earnings (with rewards): ${total_potential:,}")
        if rewards:
            print(f"  Highest single reward: ${max(rewards):,}")

        return unique_jobs

    def _scan_org(self, org: str) -> list:
        """Scan issues in an organization."""
        jobs = []
        # Get repos in org
        repos = self._get(f"{self.base_url}/orgs/{org}/repos", {"per_page": 100, "sort": "updated"})
        if not repos:
            return jobs

        for repo in repos[:10]:  # Top 10 most recently updated
            issues = self._get(f"{self.base_url}/repos/{org}/{repo['name']}/issues",
                             {"state": "open", "per_page": 20, "sort": "comments", "order": "desc"})
            if issues:
                for issue in issues:
                    job = self._evaluate_issue(issue)
                    if job and job["score"] >= 15:
                        jobs.append(job)

        return jobs

    def _scan_repo_bounties(self, repo: str) -> list:
        """Scan a specific repo for bounty-type issues."""
        owner, name = repo.split("/")
        jobs = []

        issues = self._get(f"{self.base_url}/repos/{owner}/{name}/issues",
                         {"state": "open", "per_page": 20, "sort": "comments", "order": "desc"})
        if issues:
            for issue in issues:
                job = self._evaluate_issue(issue)
                if job and job["score"] >= 20:
                    jobs.append(job)

        return jobs

    def _scan_bounty_labels(self) -> list:
        """Search across GitHub for issues with bounty labels."""
        jobs = []
        labels = ["bounty", "reward", "paid", "hacktoberfest", "up-for-grabs"]

        for label in labels:
            params = {
                "q": f"label:{label} is:issue is:open",
                "per_page": 30,
                "sort": "comments",
                "order": "desc",
            }
            results = self._get(f"{self.base_url}/search/issues", params)
            if results:
                for item in results.get("items", [])[:10]:
                    job = self._evaluate_issue(item)
                    if job and job["score"] >= 25:
                        jobs.append(job)

        return jobs

    def get_summary(self) -> dict:
        """Get a summary of current bounty state."""
        jobs = self.state.get("jobs", [])
        rewards = [j["reward"] for j in jobs if j["reward"] > 0]

        return {
            "total": len(jobs),
            "high_value": len([j for j in jobs if j["score"] >= 30]),
            "total_reward": sum(rewards),
            "avg_reward": sum(rewards) / len(rewards) if rewards else 0,
            "highest_reward": max(rewards) if rewards else 0,
            "last_scan": self.state.get("stats", {}).get("last_scan"),
            "scans": self.state.get("stats", {}).get("scans", 0),
        }

    def get_alerts(self) -> list:
        """Get highest-priority alerts (high-score jobs)."""
        jobs = self.state.get("jobs", [])
        return [j for j in jobs if j["score"] >= 30][:10]
