"""Public, signed desktop packages only; never serves knowledge or credentials."""
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix='/api/desktop/updates')
PACKAGE = re.compile(r'finesub-review-[0-9A-Za-z.+-]+-windows-x64-setup\.exe\Z')


def update_root():
    return Path(os.environ.get('DESKTOP_UPDATES_DIR', str(Path(__file__).resolve().parents[2] / 'desktop-updates'))).resolve()


def package_path(filename):
    root = update_root()
    candidate = root / filename
    if not PACKAGE.fullmatch(filename) or candidate.is_symlink() or candidate.resolve().parent != root or not candidate.is_file():
        raise HTTPException(404, '更新包不存在')
    return candidate


@router.get('/latest.json')
def latest():
    descriptor = update_root() / 'release.json'
    if not descriptor.is_file() or descriptor.is_symlink():
        raise HTTPException(503, '服务器尚未部署桌面更新包')
    try:
        if descriptor.stat().st_size > 65536:
            raise ValueError('descriptor too large')
        release = json.loads(descriptor.read_text(encoding='utf-8'))
        filename = release['filename']
        version = release['version']
        signature = release['signature']
        if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?', version):
            raise ValueError('invalid version')
        if not isinstance(filename, str) or filename != f'finesub-review-{version}-windows-x64-setup.exe':
            raise ValueError('invalid filename')
        if not isinstance(signature, str) or not re.fullmatch(r'[A-Za-z0-9+/=]+', signature):
            raise ValueError('invalid signature')
        package_path(filename)
        origin = os.environ.get('REVIEW_PUBLIC_URL', '').rstrip('/')
        url = urlsplit(origin)
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.path or url.query or url.fragment:
            raise ValueError('configure REVIEW_PUBLIC_URL as HTTPS origin')
    except (OSError, ValueError, KeyError, TypeError, HTTPException):
        raise HTTPException(503, '更新配置无效，请检查更新包与 REVIEW_PUBLIC_URL') from None
    return {
        'version': version,
        'notes': release.get('notes', ''),
        'pub_date': release.get('pub_date'),
        'platforms': {'windows-x86_64': {
            'url': f'{origin}/api/desktop/updates/files/{filename}',
            'signature': signature,
        }},
    }


@router.get('/files/{filename}')
def desktop_package(filename: str):
    return FileResponse(package_path(filename), filename=filename, media_type='application/octet-stream')
