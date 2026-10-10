"""Explicit existing-knowledge compatibility import, dry-run by default."""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

from preserved_values import apply_release, check_engine, read_archive

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--finesub-src', type=Path, required=True)
    parser.add_argument('--knowledge-root', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='Explicitly write after backup and successful dry-run')
    args = parser.parse_args()
    sys.path.insert(0, str(args.finesub_src.resolve()))
    from finesub.llm.knowledge.node.repo import KnowledgeRepo
    check_engine()  # Refuse unsupported engines before opening a writable store.
    root = args.knowledge_root.resolve()
    if not (root / 'knowledge.sqlite').is_file():
        raise ValueError('兼容工具只接受已有原生知识库，不能凭 Markdown 重建旧节点类型')
    with sqlite3.connect((root / 'knowledge.sqlite').as_uri() + '?mode=ro', uri=True) as check:
        schema = check.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    if not schema or schema[0] != '5':
        raise ValueError('兼容导入仅支持 schema 5；不会自动迁移知识库')
    rows = read_archive(args.archive)
    repo = KnowledgeRepo.open(root, auto_import=False)
    try:
        if repo.rendered_dirty_files():
            raise ValueError('rendered 存在未收录修改，请先保留并人工合并；兼容工具不会收割或覆盖这些文件，未写入')
        tasks = []
        for name, baseline, target in rows:
            category = name.split('/')[0]
            subjects = [s for s in repo.subjects(category) if s.payload['surface'] == Path(name).stem]
            if len(subjects) != 1:
                raise ValueError('兼容主体不存在或不唯一：' + name)
            tasks.append((subjects[0], baseline, target))
        result = apply_release(repo, tasks, write=args.apply)
        if args.apply:
            repo.refresh_rendered()
        print(json.dumps({'dry_run': not args.apply, 'entries': len(tasks), 'result': result,
                          'scope': 'Only manifest compatibility entries; other current-format files are not applied here.'}, ensure_ascii=False))
    finally:
        KnowledgeRepo.forget(root)

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit(str(exc)) from exc
