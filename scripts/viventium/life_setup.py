#!/usr/bin/env python3
"""Owner-only optional LIFE setup. Folder choices record intent, never access grants."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import stat
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from config_settings import load_config
from life_bootstrap import bootstrap_life

INTENT_VERSION = 1
INTENT_MAX_CHARS = 2000
BEGIN = '<!-- VIVENTIUM CONNECT INTENT START -->'
END = '<!-- VIVENTIUM CONNECT INTENT END -->'
MAX_FILE_BYTES = 1024 * 1024


def _provider_section(config, *, create):
    parent = config
    for key in ('integrations', 'glasshive', 'provider'):
        value = parent.get(key)
        if value is None and create:
            value = parent[key] = {}
        if not isinstance(value, dict):
            if create:
                raise ValueError('Life settings are invalid. Restore the configuration backup.')
            return {}
        parent = value
    return parent


def _safe_file(path):
    value = path.lstat()
    if not stat.S_ISREG(value.st_mode) or value.st_uid != os.getuid() or value.st_nlink != 1:
        raise ValueError('Life settings must be a regular file owned by you.')
    if value.st_size > MAX_FILE_BYTES:
        raise ValueError('The Life setup file is too large. Keep manual notes in a separate file.')


def _folder(raw, *, create=False):
    path = Path(raw).expanduser()
    if not path.is_absolute() or any(ord(c) < 32 for c in str(path)):
        raise ValueError('Choose an absolute folder path on this Mac.')
    # Resolve known system aliases, but reject user-selected links and linked descendants.
    if path.is_symlink():
        raise ValueError('Choose the original folder, not a symbolic link.')
    for parent in path.parents:
        if parent.is_symlink():
            raise ValueError('Choose a folder without a symbolic link in its path.')
    if create:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir():
        raise ValueError('That Life folder does not exist on this Mac yet; create it, then choose it.')
    if path.stat().st_uid != os.getuid():
        raise ValueError('Choose a folder owned by your account.')
    return path


def _root(config, state_dir):
    provider = _provider_section(config, create=False)
    value = provider.get('life_dir') or os.environ.get('VIVENTIUM_LIFE_DIR')
    return Path(value).expanduser() if value else Path.home() / 'Documents/Viventium/Life'


def intent_path(state_dir):
    """Read-only legacy location; new intent has one human-readable owner."""
    return state_dir / 'life/intent.json'


def _document(config, state_dir, *, create=False):
    root = _root(config, state_dir)
    if not root.exists() and not create:
        return root / 'Sources/WHAT_TO_CONNECT.md'
    _folder(str(root), create=create)
    sources = root / 'Sources'
    if create:
        _folder(str(sources), create=True)
    elif sources.exists():
        _folder(str(sources))
    path = sources / 'WHAT_TO_CONNECT.md'
    if path.exists() or path.is_symlink():
        _safe_file(path)
    return path


def _split_document(text):
    if BEGIN not in text and END not in text:
        return text, '', ''
    if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(BEGIN) > text.index(END):
        raise ValueError('The Life intent block is damaged. Restore its markers before saving.')
    before, rest = text.split(BEGIN, 1)
    managed, after = rest.split(END, 1)
    return before, managed, after


def _record(config, state_dir):
    path = _document(config, state_dir)
    if path.exists():
        _, managed, _ = _split_document(path.read_text(encoding='utf-8'))
        if managed:
            value = yaml.safe_load(managed)
            if not isinstance(value, dict) or value.get('version') != INTENT_VERSION:
                raise ValueError('The Life intent block is invalid. Restore it before saving.')
            return value
    legacy = intent_path(state_dir)
    if legacy.exists() or legacy.is_symlink():
        _safe_file(legacy)
        value = json.loads(legacy.read_text(encoding='utf-8'))
        if isinstance(value, dict) and value.get('version') == INTENT_VERSION:
            return {**value, 'folders': []}
    return None


def _atomic_write(path, data):
    if path.exists() or path.is_symlink():
        _safe_file(path)
    tmp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _write_record(config, state_dir, record):
    path = _document(config, state_dir, create=record is not None)
    original = path.read_text(encoding='utf-8') if path.exists() else ''
    before, managed, after = _split_document(original)
    if record is None:
        updated = before + after
    else:
        body = '\n' + yaml.safe_dump(record, sort_keys=False, allow_unicode=True)
        updated = before + BEGIN + body + END + after
    if updated != original:
        _atomic_write(path, updated)
    legacy = intent_path(state_dir)
    if legacy.exists() or legacy.is_symlink():
        _safe_file(legacy)
        legacy.unlink()


def status_payload(config, state_dir, *, show_path):
    provider = _provider_section(config, create=False)
    folder = str(provider.get('life_dir') or '').strip()
    record = _record(config, state_dir)
    payload = {'version': 1, 'enabled': bool(provider.get('life_enabled', bool(folder or record))),
               'folder_configured': bool(folder), 'folder_choice_location': 'mac',
               'intent_recorded': bool(record), 'connector': 'none'}
    if show_path:
        payload['folder'] = str(_root(config, state_dir))
    if record:
        payload['intent'] = {k: record.get(k, '') for k in ('version', 'text', 'recorded_at')}
        payload['intent']['folder_count'] = len(record.get('folders') or [])
        if show_path:
            payload['intent']['folders'] = record.get('folders') or []
    return payload


@contextmanager
def _owner_lock(config_file):
    _safe_file(config_file)
    lock = config_file.with_name('.life-setup.lock')
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        value = os.fstat(fd)
        if value.st_uid != os.getuid() or value.st_nlink != 1:
            raise ValueError('Life settings lock is not owned by you.')
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _input(args):
    if not getattr(args, 'stdin_json', False):
        return {}
    raw = sys.stdin.read(16385)
    if len(raw) > 16384:
        raise ValueError('The Life setup request is too large.')
    payload = json.loads(raw)
    if not isinstance(payload, dict) or set(payload) - {'folder', 'text', 'folders'}:
        raise ValueError('The Life setup request has unsupported fields.')
    return payload


def _execute(args):
    data = _input(args)
    if args.command == 'status':
        _safe_file(args.config_file)
        return status_payload(load_config(args.config_file), args.state_dir, show_path=args.show_path)
    config = load_config(args.config_file)
    original = yaml.safe_dump(config, sort_keys=False)
    changed = False
    if args.command == 'enable':
        folder = data.get('folder') or getattr(args, 'folder', None)
        provider = _provider_section(config, create=True)
        if folder:
            provider['life_dir'] = str(_folder(folder))
        root = _folder(str(_root(config, args.state_dir)), create=True)
        bootstrap_life(template_dir=Path(__file__).resolve().parents[2] / 'templates/life-v0.01',
                       life_dir=root.resolve(), state_file=args.state_dir / 'life/bootstrap.json')
        provider['life_enabled'] = True
    elif args.command == 'disable':
        _write_record(config, args.state_dir, None)
        _provider_section(config, create=True)['life_enabled'] = False
        changed = True
    elif args.command == 'intent':
        if args.clear:
            changed = bool(_record(config, args.state_dir))
            _write_record(config, args.state_dir, None)
        else:
            text = data.get('text', args.text or '')
            previous = _record(config, args.state_dir) or {}
            folders = data.get('folders', previous.get('folders') or [])
            if not isinstance(text, str) or len(text) > INTENT_MAX_CHARS or BEGIN in text or END in text:
                raise ValueError('Use at most 2000 characters without Life block markers.')
            if not isinstance(folders, list) or len(folders) > 32 or any(not isinstance(p, str) for p in folders):
                raise ValueError('Choose at most 32 folders on this Mac.')
            if 'folders' in data:
                folders = list(dict.fromkeys(str(_folder(p)) for p in folders))
            if not text.strip() and not folders:
                raise ValueError('Write what you may connect, choose folders, or use Clear.')
            record = {'version': INTENT_VERSION, 'text': text, 'folders': folders,
                      'recorded_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat()}
            _write_record(config, args.state_dir, record)
            _provider_section(config, create=True)['life_enabled'] = True
            changed = True
    serialized = yaml.safe_dump(config, sort_keys=False)
    if serialized != original:
        _atomic_write(args.config_file, serialized)
        changed = True
    payload = status_payload(config, args.state_dir, show_path=args.show_path)
    if args.command != 'status':
        payload['changed'] = changed
    return payload


def execute(args):
    if args.command == 'status':
        return _execute(args)
    with _owner_lock(args.config_file):
        config = load_config(args.config_file)
        paths = [args.config_file, _document(config, args.state_dir), intent_path(args.state_dir)]
        prior = {}
        for path in paths:
            if path.exists() or path.is_symlink():
                _safe_file(path)
                prior[path] = path.read_text(encoding='utf-8')
            else:
                prior[path] = None
        try:
            return _execute(args)
        except (OSError, ValueError, yaml.YAMLError):
            for path, content in prior.items():
                if content is None:
                    if path.exists():
                        _safe_file(path)
                        path.unlink()
                elif not path.exists() or path.read_text(encoding='utf-8') != content:
                    _atomic_write(path, content)
            raise


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config-file', type=Path, required=True)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--backup-dir', type=Path)  # Retained public CLI compatibility.
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--show-path', action='store_true')
    flags = argparse.ArgumentParser(add_help=False)
    for name in ('json', 'show-path', 'stdin-json'):
        flags.add_argument('--' + name, action='store_true', default=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status', parents=[flags])
    enable = sub.add_parser('enable', parents=[flags]); enable.add_argument('--folder')
    sub.add_parser('disable', parents=[flags])
    intent = sub.add_parser('intent', parents=[flags]); intent.add_argument('--text'); intent.add_argument('--clear', action='store_true')
    return parser


def main():
    args = build_parser().parse_args()
    try:
        payload = execute(args)
    except (OSError, ValueError, yaml.YAMLError) as error:
        message = str(error) if isinstance(error, ValueError) else 'Life settings could not be saved. Check folder access and available disk space.'
        if args.json:
            print(json.dumps({'error': 'life_setup_failed', 'message': message}))
        else:
            print(message, file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print('Life:', 'on' if payload['enabled'] else 'off')
        print('Folder:', payload.get('folder', 'chosen' if payload['folder_configured'] else 'default'))
        print('Intent:', (payload.get('intent') or {}).get('text') or 'none recorded')
        print('Selected folders:', (payload.get('intent') or {}).get('folder_count', 0))
        print('Nothing has been scanned or connected.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
