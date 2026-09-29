"""Deterministic source checks; no Frappe/site/database required."""
from pathlib import Path
import ast
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
files = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
counts = {'.py': 0, '.json': 0, '.js': 0}
for name in sorted(set(files)):
    path = ROOT / name
    if not path.is_file() or path.suffix not in counts:
        continue
    if path.suffix == '.py':
        ast.parse(path.read_text(), filename=name)
    elif path.suffix == '.json':
        json.loads(path.read_text())
    elif path.suffix == '.js':
        subprocess.run(['node', '--check', str(path)], check=True, stdout=subprocess.DEVNULL)
    counts[path.suffix] += 1
print('Source checks passed:', counts)
