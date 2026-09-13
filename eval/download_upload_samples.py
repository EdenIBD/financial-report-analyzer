"""Restore the direct-download samples in the saved SEC evaluation manifest.

Run from the project root. Browser saves must be acquired using Save Page As;
this script never represents a requests download as a browser save.
"""
import hashlib
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
headers = {'User-Agent': f"{os.getenv('EDGAR_USER_AGENT_NAME', 'Research User')} {os.getenv('EDGAR_USER_AGENT_EMAIL', 'research@example.com')}"}
for row in json.loads(Path('eval/upload-fixture-manifest.json').read_text()):
    if row['method'] != 'direct requests download':
        continue
    path = Path(row['path'])
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']:
        continue
    response = requests.get(row['source_url'], headers=headers, timeout=60)
    time.sleep(.25)
    response.raise_for_status()
    if hashlib.sha256(response.content).hexdigest() != row['sha256']:
        raise ValueError(f"Source bytes changed for {row['id']}; inspect before replacing evidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    print(row['id'])
