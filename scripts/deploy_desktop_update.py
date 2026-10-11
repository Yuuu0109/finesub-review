"""Validate CI artifact checksums and publish metadata last. Keeps older installers."""
import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path


def deploy(source: Path, destination: Path):
    source, destination = source.resolve(), destination.resolve()
    release = json.loads((source / 'release.json').read_text(encoding='utf-8'))
    name = release['filename']
    version = release['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?', version) or name != f'finesub-review-{version}-windows-x64-setup.exe':
        raise ValueError('Invalid release filename/version')
    expected = {name, name + '.sig', 'release.json'}
    checksums = {}
    for line in (source / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        digest, filename = line.split('  ', 1)
        if filename not in expected or filename in checksums or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ValueError('Invalid checksum manifest')
        checksums[filename] = digest
    if set(checksums) != expected:
        raise ValueError('Incomplete checksum manifest')
    for filename, digest in checksums.items():
        if (source / filename).is_symlink() or hashlib.sha256((source / filename).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Checksum mismatch: {filename}')
    if (source / (name + '.sig')).read_text().strip() != release['signature'] or checksums[name] != release['sha256']:
        raise ValueError('Release metadata does not match installer')
    destination.mkdir(parents=True, exist_ok=True)
    for filename in [name, name + '.sig', 'SHA256SUMS.txt', 'release.json']:
        # Atomic replacement within destination filesystem. Publish release.json last.
        fd, temp = tempfile.mkstemp(prefix='.update-', dir=destination)
        os.close(fd)
        try:
            shutil.copyfile(source / filename, temp)
            os.chmod(temp, 0o644)
            os.replace(temp, destination / filename)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    return version


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, default=Path('desktop-updates'))
    args = parser.parse_args()
    print(f'Published desktop update {deploy(args.source, args.destination)} to {args.destination.resolve()}')
