import json

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def updates(tmp_path, monkeypatch):
    monkeypatch.setenv('DESKTOP_UPDATES_DIR', str(tmp_path))
    monkeypatch.setenv('REVIEW_PUBLIC_URL', 'https://review.example.com')
    filename = 'finesub-review-0.2.0-windows-x64-setup.exe'
    (tmp_path / filename).write_bytes(b'MZ-test-package')
    record = {'version': '0.2.0', 'filename': filename, 'signature': 'dGVzdA==', 'notes': '更新测试', 'pub_date': '2026-10-11T00:00:00Z'}
    (tmp_path / 'release.json').write_text(json.dumps(record), encoding='utf-8')
    return tmp_path, record


def test_manifest_and_binary_are_public_but_knowledge_is_not(updates):
    c = TestClient(app)
    response = c.get('/api/desktop/updates/latest.json')
    assert response.status_code == 200
    platform = response.json()['platforms']['windows-x86_64']
    assert platform['url'].startswith('https://review.example.com/api/desktop/updates/files/')
    assert response.headers['cache-control'] == 'no-store'
    download = c.get('/api/desktop/updates/files/' + updates[1]['filename'])
    assert download.content == b'MZ-test-package'
    assert c.get('/api/entries').status_code == 401


def test_missing_update_is_not_reported_as_latest(tmp_path, monkeypatch):
    monkeypatch.setenv('DESKTOP_UPDATES_DIR', str(tmp_path))
    assert TestClient(app).get('/api/desktop/updates/latest.json').status_code == 503


@pytest.mark.parametrize('origin', ['', 'http://example.com', 'https://u:p@example.com', 'https://example.com/path'])
def test_rejects_invalid_public_origin(updates, monkeypatch, origin):
    monkeypatch.setenv('REVIEW_PUBLIC_URL', origin)
    assert TestClient(app).get('/api/desktop/updates/latest.json').status_code == 503


def test_download_cannot_read_other_files(updates):
    root, _ = updates
    (root / 'secret.key').write_text('must not be served')
    c = TestClient(app)
    for name in ['secret.key', 'release.json', '..%2F.env', 'missing.exe']:
        assert c.get('/api/desktop/updates/files/' + name).status_code == 404


def test_invalid_descriptor_or_missing_installer_fails_closed(updates):
    root, record = updates
    (root / record['filename']).unlink()
    assert TestClient(app).get('/api/desktop/updates/latest.json').status_code == 503
    (root / 'release.json').write_text('invalid JSON')
    assert TestClient(app).get('/api/desktop/updates/latest.json').status_code == 503
