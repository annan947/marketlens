"""Audit Git content without printing secret values. A heuristic, not a guarantee."""
import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'GitHub token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),
    'AWS access key': re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'provider secret key': re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b'),
    'assigned credential': re.compile(r'''(?im)^\s*(?:[A-Z_]*(?:API_KEY|SECRET_KEY|ACCESS_TOKEN|AUTH_TOKEN|PASSWORD))\s*[:=]\s*["']?([A-Za-z0-9_+/=-]{24,})'''),
    'credential URI': re.compile(r'(?i)(?:postgres(?:ql)?(?:\+psycopg)?|mysql|mongodb(?:\+srv)?)://[^\s/:]+:([^\s@]+)@'),
}
PLACEHOLDERS = {'password', 'secret', 'pass', 'test', 'marketlens_test', 'replace-with-a-long-random-hex-password'}


def findings(path, content):
    parts = Path(path).parts
    name = Path(path).name
    issues = []
    if (name.startswith('.env') and name != '.env.example') or name in {'.npmrc', '.netrc', '.pypirc'} or any(part in {'.venv', 'node_modules', 'secrets', 'credentials', 'data', 'downloads', 'work'} for part in parts):
        issues.append('private/generated path tracked')
    for label, pattern in PATTERNS.items():
        for match in pattern.finditer(content):
            if label in {'credential URI', 'assigned credential'}:
                value = match.group(1)
                if value in PLACEHOLDERS or any(char in value for char in '${}<>'):
                    continue
            issues.append(label)
            break
    return issues


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--history', action='store_true', help='Also scan every reachable commit')
    args = parser.parse_args()
    files = git('ls-files', '-z').decode().split('\0')
    entries = [(':', path) for path in files if path]
    if args.history:
        for revision in git('rev-list', '--all').decode().splitlines():
            paths = git('ls-tree', '-r', '--name-only', '-z', revision).decode().split('\0')
            entries.extend((revision+':', path) for path in paths if path)
    seen = set()
    failures = []
    for revision, path in entries:
        data = git('show', revision+path)
        key = (path, data)
        if key in seen:
            continue
        seen.add(key)
        for issue in findings(path, data.decode('utf-8', errors='replace')):
            failures.append((path, issue))
    for path, issue in sorted(set(failures)):
        print(f'REVIEW: {path}: {issue} (value redacted)')
    print(f'Audited {len(seen)} unique Git file versions; {len(set(failures))} findings.')
    return int(bool(failures))


if __name__ == '__main__':
    sys.exit(main())
