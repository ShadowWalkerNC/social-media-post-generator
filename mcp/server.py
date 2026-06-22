"""
server.py -- Post-Pilot MCP Server

Exposes audit and fix tools for use in Claude Desktop, Cursor, Windsurf,
or any MCP-compatible client.

Setup:
    pip install mcp PyGithub
    export GITHUB_TOKEN=your_personal_access_token

Run (stdio, for Claude Desktop / Cursor):
    python mcp/server.py

Run (HTTP, for hosted/shared use):
    python mcp/server.py --transport sse --port 8001

Add to Claude Desktop (~/Library/Application Support/Claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "post-pilot": {
          "command": "python",
          "args": ["/absolute/path/to/Post-Pilot/mcp/server.py"],
          "env": { "GITHUB_TOKEN": "your_token_here" }
        }
      }
    }
"""

import os
import sys
import logging
from datetime import datetime

# Ensure repo root is on the path so we can import modules/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mcp.server.fastmcp import FastMCP
from github import Github, GithubException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('postpilot-mcp')

mcp = FastMCP(
    name='post-pilot',
    description='Audit and fix tools for the Post-Pilot social media SaaS repo.',
)


def _gh(owner: str, repo: str):
    """Return an authenticated PyGithub repo object."""
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        raise RuntimeError('GITHUB_TOKEN environment variable not set.')
    return Github(token).get_repo(f'{owner}/{repo}')


# ---------------------------------------------------------------------------
# Tool 1: Repo structure snapshot
# ---------------------------------------------------------------------------
@mcp.tool()
def get_repo_structure(owner: str, repo: str) -> dict:
    """
    Return a top-level file/directory listing for a GitHub repo.
    Use this before running an audit to confirm the repo layout.
    """
    r = _gh(owner, repo)
    contents = r.get_contents('')
    return {
        'repo':  f'{owner}/{repo}',
        'files': [
            {'name': c.name, 'type': c.type, 'size': c.size}
            for c in contents
        ],
    }


# ---------------------------------------------------------------------------
# Tool 2: Read any file
# ---------------------------------------------------------------------------
@mcp.tool()
def read_file(owner: str, repo: str, path: str) -> dict:
    """
    Read the contents of any file in the repo.
    Use this to inspect code before suggesting or applying fixes.
    """
    r    = _gh(owner, repo)
    file = r.get_contents(path)
    return {
        'path':    path,
        'sha':     file.sha,
        'content': file.decoded_content.decode('utf-8', errors='replace'),
    }


# ---------------------------------------------------------------------------
# Tool 3: Audit checklist
# ---------------------------------------------------------------------------
@mcp.tool()
def audit_repo(owner: str, repo: str) -> dict:
    """
    Run a lightweight automated audit of the repo.
    Checks for: test directory, CI pipeline, requirements completeness,
    db.py abstraction, plan_guard, scheduler_worker, TODO.md.
    Returns a checklist with pass/fail per item.
    """
    r       = _gh(owner, repo)
    results = {}

    checks = [
        ('tests/ directory',    'tests'),
        ('CI pipeline',         '.github/workflows/ci.yml'),
        ('db.py abstraction',   'modules/db.py'),
        ('plan_guard.py',       'modules/plan_guard.py'),
        ('scheduler_worker.py', 'modules/scheduler_worker.py'),
        ('TODO.md',             'TODO.md'),
        ('requirements.txt',    'requirements.txt'),
    ]

    for label, path in checks:
        try:
            r.get_contents(path)
            results[label] = 'PASS'
        except GithubException:
            results[label] = 'MISSING'

    # Check requirements for key packages
    try:
        req_text = r.get_contents('requirements.txt').decoded_content.decode()
        for pkg in ['psycopg2', 'APScheduler', 'pytest', 'sentry-sdk']:
            results[f'requirements: {pkg}'] = 'PASS' if pkg in req_text else 'MISSING'
    except GithubException:
        results['requirements.txt'] = 'MISSING'

    passed = sum(1 for v in results.values() if v == 'PASS')
    total  = len(results)

    return {
        'repo':    f'{owner}/{repo}',
        'audited': datetime.utcnow().isoformat() + 'Z',
        'score':   f'{passed}/{total}',
        'checks':  results,
    }


# ---------------------------------------------------------------------------
# Tool 4: Write / update a single file
# ---------------------------------------------------------------------------
@mcp.tool()
def write_file(owner: str, repo: str, path: str, content: str, commit_message: str) -> dict:
    """
    Create or update a single file in the repo.
    Automatically fetches the current SHA if the file already exists.
    Use this to apply targeted fixes.
    """
    r   = _gh(owner, repo)
    sha = None
    try:
        sha = r.get_contents(path).sha
    except GithubException:
        pass  # new file

    if sha:
        result = r.update_file(path, commit_message, content, sha)
    else:
        result = r.create_file(path, commit_message, content)

    return {
        'path':       path,
        'commit_sha': result['commit'].sha,
        'html_url':   result['commit'].html_url,
    }


# ---------------------------------------------------------------------------
# Tool 5: List open issues
# ---------------------------------------------------------------------------
@mcp.tool()
def list_open_issues(owner: str, repo: str, label: str = None) -> list:
    """
    List open GitHub issues, optionally filtered by label.
    Useful for cross-referencing audit findings with existing tickets.
    """
    r      = _gh(owner, repo)
    kwargs = {'state': 'open'}
    if label:
        kwargs['labels'] = [label]
    issues = r.get_issues(**kwargs)
    return [
        {
            'number': i.number,
            'title':  i.title,
            'url':    i.html_url,
            'labels': [l.name for l in i.labels],
        }
        for i in list(issues)[:25]
    ]


# ---------------------------------------------------------------------------
# Tool 6: Create a GitHub issue from an audit finding
# ---------------------------------------------------------------------------
@mcp.tool()
def create_issue(owner: str, repo: str, title: str, body: str, labels: list = None) -> dict:
    """
    Create a GitHub issue. Use this to track audit findings that
    need manual attention (e.g. Railway Postgres setup).
    """
    r     = _gh(owner, repo)
    issue = r.create_issue(
        title=title,
        body=body,
        labels=labels or [],
    )
    return {
        'number':   issue.number,
        'title':    issue.title,
        'html_url': issue.html_url,
    }


# ---------------------------------------------------------------------------
# Tool 7: List recent commits
# ---------------------------------------------------------------------------
@mcp.tool()
def list_recent_commits(owner: str, repo: str, branch: str = 'main', limit: int = 10) -> list:
    """
    Return the N most recent commits on a branch.
    Use this to verify that fix commits landed correctly.
    """
    r       = _gh(owner, repo)
    commits = r.get_commits(sha=branch)
    return [
        {
            'sha':     c.sha[:7],
            'message': c.commit.message.splitlines()[0],
            'author':  c.commit.author.name,
            'date':    c.commit.author.date.isoformat(),
            'url':     c.html_url,
        }
        for c in list(commits)[:limit]
    ]


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--transport', default='stdio', choices=['stdio', 'sse'])
    parser.add_argument('--port', type=int, default=8001)
    args = parser.parse_args()

    if args.transport == 'sse':
        mcp.run(transport='sse', port=args.port)
    else:
        mcp.run(transport='stdio')
