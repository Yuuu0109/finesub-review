"""Review navigation and publication readiness use the same version boundaries."""
from sqlalchemy import select

from app.db import Revision, Session
from app.worker import run_once
from test_workflow import approve, client, document, isolated_database, latest, publish, upload


def test_personal_review_filter_ignores_replies_and_other_members_and_resets_on_revision():
    a, m, other = client(), client('member'), client('member')
    upload(a)
    entry = latest(a)
    path = f'/api/entries/{entry["entry_id"]}'
    record = other.post(path + '/reviews', json={'revision_id': entry['id'], 'verdict': 'approve', 'body': '已核对'}).json()
    m.post(path + '/reviews', json={'revision_id': entry['id'], 'parent_id': record['id'], 'verdict': 'reply', 'body': '回复不算审核'})
    assert m.get('/api/entries?reviewed=no').json()['total'] == 1
    assert other.get('/api/entries?reviewed=no').json()['total'] == 0
    m.post(path + '/reviews', json={'revision_id': entry['id'], 'verdict': 'changes', 'body': '补充出处'})
    assert m.get('/api/entries?reviewed=yes').json()['items'][0]['my_review']
    assert m.get('/api/entries?reviewed=no').json()['total'] == 0
    revised = a.post(path + '/revisions', json={'base_revision': entry['id'], 'content': document(extra='- 新出处。')})
    assert revised.status_code == 200
    assert m.get('/api/entries?reviewed=no').json()['total'] == 1
    assert not m.get('/api/entries').json()['items'][0]['my_review']


def test_cursor_does_not_skip_after_decision_and_preserves_scope():
    a = client()
    batch = upload(a, {f'common/词条{i}.md': document(f'词条{i}') for i in range(4)})
    upload(a, {'common/其他批次.md': document('其他批次')})
    # Equal timestamps must still yield a deterministic, complete traversal.
    with Session.begin() as db:
        for rev in db.scalars(select(Revision)).all():
            rev.created_at = '2026-10-22T00:00:00+00:00'
    url = f'/api/entries?status=pending&category=common&batch_id={batch["id"]}'
    ordered = a.get(url).json()['items']
    assert len(ordered) == 4
    for index, item in enumerate(ordered):
        approve(a, item)
        result = a.get(url + f'&after={item["id"]}&limit=1').json()
        assert [r['id'] for r in result['items']] == ([ordered[index + 1]['id']] if index < 3 else [])
    assert a.get(url + f'&after={ordered[0]["id"]}&page=2').status_code == 422
    assert a.get('/api/entries?after=missing').status_code == 404


def test_diff_can_compare_to_published_instead_of_previous_revision():
    a = client()
    upload(a)
    first = latest(a)
    approve(a, first)
    publish(a, [first])
    path = f'/api/entries/{first["entry_id"]}'
    second = a.post(path + '/revisions', json={'base_revision': first['id'], 'content': document(extra='- 第二版新增依据。')}).json()
    third = a.post(path + '/revisions', json={'base_revision': second['id'], 'content': document(extra='- 第二版新增依据。\n- 第三版补充。')}).json()
    previous = a.get(path).json()
    formal = a.get(path + '?compare_to=published').json()
    assert previous['comparison']['id'] == second['id']
    assert formal['comparison']['id'] == first['id']
    assert '+- 第二版新增依据。' not in previous['diff']
    assert '+- 第二版新增依据。' in formal['diff']
    assert formal['entry']['id'] == third['id']
    assert a.get(path + '?compare_to=unknown').status_code == 422
