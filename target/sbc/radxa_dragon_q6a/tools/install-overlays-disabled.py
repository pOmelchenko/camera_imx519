#!/usr/bin/env python3
"""Install Q6A camera overlays as .dtbo.disabled, without changing boot config."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo after building and checking the overlays.')
    if not args.kernel or Path(args.kernel).name != args.kernel or args.kernel in ('.', '..'):
        raise SystemExit('Invalid kernel name')
    destination = Path('/boot/efi/RadxaOS') / args.kernel / 'dtbo'
    if not destination.is_dir():
        raise SystemExit(f'RadxaOS overlay directory does not exist: {destination}')
    build = Path(__file__).resolve().parents[1] / 'build'
    pairs = [(build / f'imx519-cam{port}.dtbo',
              destination / f'imx519-cam{port}.dtbo.disabled') for port in (1, 2, 3)]
    # Validate every destination before making any changes.
    for source, target in pairs:
        if not source.is_file():
            raise SystemExit(f'Missing build: {source}')
        if target.is_symlink() or target.with_suffix('').exists():
            raise SystemExit(f'Overlay already enabled or symlinked: {target}')
        if target.exists() and digest(target) != digest(source):
            raise SystemExit(f'Different installed overlay exists; preserve it first: {target}')
    active = {path.name: digest(path) for path in destination.glob('*.dtbo')}
    boot_root = Path('/boot/efi/loader/entries')
    entries = {path: path.read_bytes() for path in boot_root.glob('*.conf')}
    for source, target in pairs:
        if not target.exists():
            with target.open('xb') as output:
                output.write(source.read_bytes())
            shutil.copymode(source, target)
        print(f'{target}: disabled, SHA-256 {digest(target)}')
    if active != {path.name: digest(path) for path in destination.glob('*.dtbo')}:
        raise RuntimeError('Active overlay inventory changed during installation')
    if any(path.read_bytes() != content for path, content in entries.items()):
        raise RuntimeError('Boot entry changed during installation')
    print('Active overlays and boot entries unchanged. No reboot or activation performed.')


if __name__ == '__main__':
    main()
