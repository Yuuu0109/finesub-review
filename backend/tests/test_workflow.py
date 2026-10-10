import io
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ['REVIEW_DATA_DIR'] = str(ROOT / 'test-results' / 'db')
test_url = os.environ.get('TEST_DATABASE_URL')
if test_url:
    if not test_url.rsplit('/', 1)[-1].endswith('_test'):
        raise RuntimeError('Integration tests require a dedicated database ending in _test')
    os.environ['DATABASE_URL'] = test_url
else:
    os.environ['DATABASE_URL'] = f'sqlite:///{ROOT / "test-results" / "db" / "test.db"}'

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import compat
from app.db import AccessGate, AccessSession, Base, Batch, Entry, ImportItem, Job, LoginSession, Release, Review, Revision, Session, User, engine, init_db
from app.main import app
from app.security import hash_password
from app.worker import run_once

PASSWORD = 'Test-only-password-2026'
PASSPHRASE = 'Test-only-access-2026'


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.drop_all(engine)
    init_db()
    with Session.begin() as db:
        db.add(AccessGate(id=1, passphrase_hash=hash_password(PASSPHRASE)))
        db.add_all([User(username='admin', name='管理员', role='admin', password=hash_password(PASSWORD)),
                    User(username='member', name='审核成员', role='member', password=hash_password(PASSWORD))])
    yield


def client(username='admin'):
    c = TestClient(app)
    response = c.post('/api/auth/enter', json={'passphrase': PASSPHRASE})
    assert response.status_code == 200, response.text
    c.headers['X-CSRF-Token'] = response.json()['csrf']
    if username == 'admin':
        response = c.post('/api/auth/login', json={'username': username, 'password': PASSWORD})
        assert response.status_code == 200, response.text
        c.headers['X-CSRF-Token'] = response.json()['csrf']
    return c


def document(name='暖柑好', extra='', kind='梗'):
    return f'# {name}\n节目中的问候语。\n\n## 档案\n本名: {name}\n别名: 辛苦柑\n类型: {kind}\n\n## 用法\n- 来源：第 20 期 12:34。\n{extra}\n## 元数据\n最近更新日期: 2026-09-17\n'


def upload(c, files=None, confirm=True, filename='knowledge.zip'):
    files = files or {'common/暖柑好.md': document()}
    payload = compat.make_zip(files) if filename.endswith('.zip') else next(iter(files.values())).encode()
    result = c.post('/api/imports', data={'name': '测试批次', 'source': '第 20 期'}, files=[('files', (filename, payload, 'application/octet-stream'))])
    assert result.status_code == 200, result.text
    batch_id = result.json()['id']
    assert run_once()
    batch = c.get('/api/imports/' + batch_id).json()
    if confirm:
        ids = [item['id'] for item in batch['items'] if not item['error'] and item['classification'] != 'duplicate']
        if ids:
            response = c.post('/api/imports/' + batch_id + '/confirm', json={'item_ids': ids})
            assert response.status_code == 200, response.text
    return batch


def latest(c):
    return c.get('/api/entries').json()['items'][0]


def approve(c, entry):
    result = c.post(f'/api/entries/{entry["entry_id"]}/decision', json={'revision_id': entry['id'], 'status': 'approved', 'reason': '已核对来源'})
    assert result.status_code == 200, result.text


def publish(c, entries, run=True):
    result = c.post('/api/releases', json={'name': '正式版本', 'revision_ids': [e['id'] for e in entries]})
    assert result.status_code == 200, result.text
    if run:
        assert run_once()
    return result.json()['id']


def zip_files(c, release):
    response = c.get(f'/api/releases/{release}/download')
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        return {p: z.read(p).decode() for p in z.namelist()}


def test_member_records_never_decide_and_admin_needs_no_votes():
    a, m = client(), client('member')
    upload(a)
    entry = latest(a)
    r = m.post(f'/api/entries/{entry["entry_id"]}/reviews', json={'revision_id': entry['id'], 'verdict': 'reject', 'body': '需要核实语境'})
    assert r.status_code == 200
    assert latest(a)['status'] == 'pending'
    approve(a, entry)
    assert latest(a)['status'] == 'approved'
    upload(a, {'common/另一个词条.md': document('另一个词条')})
    new = latest(a)
    assert new['review_count'] == 0
    approve(a, new)
    assert latest(a)['status'] == 'approved'


def test_member_cannot_import_edit_decide_publish_manage_or_download():
    a, m = client(), client('member')
    upload(a)
    entry = latest(a)
    endpoints = [('/api/users', {'username': 'evil', 'name': '越权', 'password': PASSWORD}),
                 (f'/api/entries/{entry["entry_id"]}/decision', {'revision_id': entry['id'], 'status': 'approved', 'reason': '越权'}),
                 (f'/api/entries/{entry["entry_id"]}/revisions', {'base_revision': entry['id'], 'content': document()}),
                 ('/api/releases', {'name': '越权发布', 'revision_ids': [entry['id']]})]
    for path, body in endpoints:
        assert m.post(path, json=body).status_code == 403
    assert m.post('/api/imports', data={'name': '越权'}, files={'files': ('a.md', b'# a')}).status_code == 403
    approve(a, entry)
    rid = publish(a, [entry])
    assert m.get(f'/api/releases/{rid}/download').status_code == 403
    assert m.get('/api/audit').status_code == 403


def test_csrf_and_unknown_roles_rejected():
    a = client()
    assert a.post('/api/users', json={'username': 'reader', 'name': '读者', 'password': PASSWORD, 'role': 'viewer'}).status_code == 422
    a.headers.pop('X-CSRF-Token')
    assert a.post('/api/auth/logout').status_code == 403
    assert a.get('/api/auth/me').status_code == 200


def test_revision_invalidates_decision_and_preserves_historical_record():
    a, m = client(), client('member')
    upload(a)
    entry = latest(a)
    m.post(f'/api/entries/{entry["entry_id"]}/reviews', json={'revision_id': entry['id'], 'verdict': 'approve', 'body': '核对过旧版本'})
    approve(a, entry)
    result = a.post(f'/api/entries/{entry["entry_id"]}/revisions', json={'base_revision': entry['id'], 'content': document(extra='- 新依据。')})
    assert result.status_code == 200
    assert result.json()['status'] == 'pending'
    detail = a.get(f'/api/entries/{entry["entry_id"]}').json()
    assert detail['reviews'][0]['stale'] is True
    assert detail['decisions'][0]['revision_id'] == entry['id']
    assert a.post(f'/api/entries/{entry["entry_id"]}/decision', json={'revision_id': entry['id'], 'status': 'approved', 'reason': '过期决定'}).status_code == 409
    assert a.post('/api/releases', json={'name': '过期版本', 'revision_ids': [entry['id']]}).status_code == 409


def test_duplicate_upload_and_import_confirmation_are_idempotent():
    a = client()
    first = upload(a)
    second = upload(a, confirm=False)
    assert second['items'][0]['classification'] == 'duplicate'
    assert a.get('/api/entries').json()['total'] == 1
    response = a.post('/api/imports/' + first['id'] + '/confirm', json={'item_ids': [first['items'][0]['id']]})
    assert response.status_code == 200 and response.json()['created'] == 0


def test_conflicting_preview_does_not_overwrite_new_revision():
    a = client()
    upload(a)
    old = latest(a)
    preview = upload(a, {'common/暖柑好.md': document(extra='- 导入修改')}, confirm=False)
    a.post(f'/api/entries/{old["entry_id"]}/revisions', json={'base_revision': old['id'], 'content': document(extra='- 人工修改')})
    response = a.post('/api/imports/' + preview['id'] + '/confirm', json={'item_ids': [preview['items'][0]['id']]})
    assert response.status_code == 409
    assert '人工修改' in a.get('/api/entries/' + old['entry_id']).json()['entry']['content']


def test_release_preserves_baseline_excludes_unapproved_and_rollback_is_new_version():
    a = client()
    upload(a)
    first = latest(a)
    approve(a, first)
    release1 = publish(a, [first])
    upload(a, {'common/新知识.md': document('新知识'), 'common/未审知识.md': document('未审知识')})
    rows = a.get('/api/entries').json()['items']
    second = next(e for e in rows if e['title'] == '新知识')
    approve(a, second)
    release2 = publish(a, [second])
    files = zip_files(a, release2)
    assert 'common/暖柑好.md' in files and 'common/新知识.md' in files
    assert 'common/未审知识.md' not in files
    assert '暖柑好' in files['common/index.md'] and '新知识' in files['common/index.md']
    r = a.post('/api/releases', json={'name': '回退验证', 'rollback_id': release1, 'notes': '恢复原始版本'})
    assert r.status_code == 200
    assert run_once()
    assert r.json()['id'] not in (release1, release2)
    assert 'common/新知识.md' not in zip_files(a, r.json()['id'])
    assert zip_files(a, release1)['common/暖柑好.md'] == document()


def test_queued_release_rechecks_approval_and_current_version():
    a = client()
    upload(a)
    entry = latest(a)
    approve(a, entry)
    rid = publish(a, [entry], run=False)
    a.post(f'/api/entries/{entry["entry_id"]}/revisions', json={'base_revision': entry['id'], 'content': document(extra='- 新修订')})
    assert run_once()
    assert a.get('/api/releases').json()[0]['status'] == 'failed'
    assert a.get(f'/api/releases/{rid}/download').status_code == 409


def test_delete_is_explicit_reviewed_and_not_repeated_after_publication():
    a = client()
    upload(a)
    entry = latest(a)
    approve(a, entry)
    publish(a, [entry])
    r = a.post(f'/api/entries/{entry["entry_id"]}/revisions', json={'base_revision': entry['id'], 'content': document(), 'operation': 'delete'}).json()
    approve(a, r)
    rid = publish(a, [r])
    assert 'common/暖柑好.md' not in zip_files(a, rid)
    assert latest(a)['published'] is True
    assert a.get('/api/dashboard').json()['pending_publish'] == 0


def test_translation_records_split_and_featured_limit_and_references():
    a = client()
    content = '# 常见翻译错误\n\n## 精选\n\n- M0001\n\n## 条目\n\n### M0001\n- 原文片段: `縁側`\n- 错误译文: `走廊`\n- 正确译文: `鱼鳍肉`\n- 说明: 寿司语境\n- 记录时间: 2026-09\n'
    upload(a, {'translation/common-mistake.md': content})
    rows = a.get('/api/entries').json()['items']
    assert len(rows) == 2
    for e in rows:
        approve(a, e)
    rid = publish(a, rows)
    files = zip_files(a, rid)
    assert '### M0001' in files['translation/common-mistake.md']
    assert '- M0001' in files['translation/common-mistake.md']
    _, report = compat.build_files({'translation/featured.md': '# 精选\n- M9999\n'}, 'legacy-preserve')
    assert report['errors']
    _, errors = compat.validate('translation/featured.md', '# 精选\n' + '\n'.join(f'- M{i:04}' for i in range(31)))
    assert errors


@pytest.mark.parametrize('filename', ['../escape.md','/absolute.md','C:/escape.md','common/../../escape.md','common/CON.md'])
def test_unsafe_zip_paths_rejected(filename):
    data = compat.make_zip({filename: '# escape'})
    with pytest.raises(ValueError):
        compat.unpack('test.zip', data)


def test_zip_symlink_and_bad_encoding_rejected():
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        item = zipfile.ZipInfo('common/link.md')
        item.create_system = 3
        item.external_attr = 0o120777 << 16
        z.writestr(item, '/etc/passwd')
    with pytest.raises(ValueError):
        compat.unpack('test.zip', out.getvalue())
    with pytest.raises(ValueError):
        compat.text_decode(b'\xff\xfe\x00')


def test_jsonl_edit_requires_snapshot_and_rename_keeps_identity():
    import json
    a = client()
    upload(a)
    original = latest(a)
    missing = json.dumps({'category': 'common', 'entry': '暖柑好', 'op': 'edit_lines', 'edits': [{'action': 'change', 'line': 2, 'content': '新简介'}]}, ensure_ascii=False)
    with pytest.raises(ValueError, match='base_sha256'):
        compat.proposals(missing, {'common/暖柑好.md': document()})
    rename = json.dumps({'category': 'common', 'entry': '暖柑好', 'op': 'rename_entry', 'new_key': '新问候'}, ensure_ascii=False)
    upload(a, {'proposal': rename}, filename='changes.jsonl')
    renamed = latest(a)
    assert renamed['entry_id'] == original['entry_id']
    assert renamed['path'] == 'common/新问候.md'
    assert renamed['number'] == 2


def test_disabled_account_loses_existing_session():
    a, m = client(), client('member')
    member = m.get('/api/auth/me').json()['user']
    assert a.patch('/api/users/' + member['id'], json={'active': False, 'role': 'member'}).status_code == 200
    assert m.get('/api/entries').status_code == 401


def test_actual_knowledge_round_trip_if_fixture_available():
    root = Path(os.environ.get('REVIEW_KNOWLEDGE_TEST_ROOT', str(ROOT.parent / 'knowledge')))
    if not root.exists():
        pytest.skip('Local real-world knowledge fixture not available')
    a = client()
    source = {p.relative_to(root).as_posix(): p.read_text(encoding='utf-8-sig') for p in root.rglob('*.md') if '.git' not in p.parts}
    batch = upload(a, source)
    assert not [item for item in batch['items'] if item['error']]
    rows = a.get('/api/entries?limit=100').json()['items']
    assert len(rows) >= 47
    for entry in rows:
        approve(a, entry)
    rid = publish(a, rows)
    exported = zip_files(a, rid)
    (ROOT / 'test-results' / 'native-export.zip').write_bytes(a.get(f'/api/releases/{rid}/download').content)
    projection = root / 'rendered' if (root / 'rendered').is_dir() else root
    for category in ('common', 'streamer'):
        for file in (projection / category).glob('*.md'):
            if file.name != 'index.md':
                assert exported[f'{category}/{file.name}'] == file.read_text(encoding='utf-8-sig')
    assert 'translation/common-mistake.md' in exported


def test_native_mistake_proposals_and_ids_not_reused():
    import json
    payload = {'op': 'add_mistake', 'source': '縁側', 'wrong': '走廊', 'correct': '鱼鳍肉', 'note': '寿司语境'}
    result = compat.proposals(json.dumps(payload, ensure_ascii=False), {}, reserved_paths=['translation/mistakes/M0005.md'])
    assert result[0]['path'] == 'translation/mistakes/M0006.md'
    with pytest.raises(ValueError, match='不存在'):
        compat.proposals(json.dumps({'op': 'set_featured', 'ids': ['M9999']}), {})


def test_jsonl_dependent_group_cannot_be_partially_published():
    import json
    a = client()
    payload = '\n'.join(json.dumps({'category': 'common', 'entry': name, 'op': 'create_entry', 'entry_type': '梗', 'intro': '节目问候', 'reason': '独立节目问候具有持续积累价值，无法并入已有词条'}, ensure_ascii=False) for name in ('甲', '乙'))
    upload(a, {'proposal': payload}, filename='changes.jsonl')
    rows = a.get('/api/entries').json()['items']
    for row in rows:
        approve(a, row)
    assert a.post('/api/releases', json={'name': '部分发布', 'revision_ids': [rows[0]['id']]}).status_code == 409
    publish(a, rows)


def test_worker_recovers_abandoned_job_and_keeps_results_unique():
    from datetime import datetime, timedelta, timezone
    a = client()
    response = a.post('/api/imports', data={'name': '中断测试'}, files={'files': ('resume.zip', compat.make_zip({'common/暖柑好.md': document()}))})
    bid = response.json()['id']
    with Session.begin() as db:
        job = db.scalar(select(Job).where(Job.target_id == bid))
        job.status = 'processing'
        job.touched_at = (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()
    assert run_once()
    result = a.get('/api/imports/' + bid).json()
    assert result['status'] == 'preview' and len(result['items']) == 1
    assert run_once() is False


def test_quote_must_match_version_and_role_escalation_fields_rejected():
    a, m = client(), client('member')
    upload(a)
    entry = latest(a)
    body = {'revision_id': entry['id'], 'verdict': 'approve', 'body': '测试', 'quote': '并不存在的原文'}
    assert m.post(f'/api/entries/{entry["entry_id"]}/reviews', json=body).status_code == 422
    body.pop('quote')
    body['status'] = 'approved'
    assert m.post(f'/api/entries/{entry["entry_id"]}/reviews', json=body).status_code == 422
