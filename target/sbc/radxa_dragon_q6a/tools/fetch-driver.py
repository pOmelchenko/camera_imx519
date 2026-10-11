#!/usr/bin/env python3
"""Fetch pinned, hash-checked IMX519 and AK7375 driver sources."""
import hashlib
import json
from pathlib import Path
import urllib.request

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'sources.json').read_text(encoding='utf-8'))
destination = root / 'vendor'
destination.mkdir(exist_ok=True)

for source in manifest['driver']['files']:
    target = destination / source['path']
    assert target.parent == destination, 'Driver cache must remain in vendor/'
    if target.exists():
        data = target.read_bytes()
        if hashlib.sha256(data).hexdigest() != source['sha256']:
            raise SystemExit(f'{target}: hash mismatch; preserve and inspect the local file')
    else:
        request = urllib.request.Request(source['url'], headers={'User-Agent': 'camera-imx519-q6a'})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != source['sha256']:
            raise SystemExit(f'{source["url"]}: downloaded hash mismatch')
        with target.open('xb') as output:
            output.write(data)
    print(f'{source["path"]}: SHA-256 verified')
