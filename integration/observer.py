#!/usr/bin/env python3
"""Explicit review/apply interface; passive hooks never control the main task."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from common import ROOT, now, read_json, skill, startup, state, workspace
from collector import capture, finish_batch, harvest
from installer import apply, make_plan, recover, register
from demo import prepare_demo


def status(root):
    base = state(root)
    batches = [read_json(p) for p in sorted((base / 'batches').glob('*/batch.json'))]
    pending = [b for b in batches if b['state'] != 'reviewed']
    installs = []
    for p in (base / 'batches').glob('*/plan.json'):
        receipt = read_json(p.parent / 'APPLY.json', {})
        if receipt.get('state') != 'complete':
            installs.append({'batch': p.parent.name, 'state': receipt.get('state', 'staged'),
                             'receipt': str(p.parent / 'APPLY.json')})
    sources = [read_json(p) for p in (base / 'sources').glob('*.json')]
    return {'plugin_version': '3.8.4', 'candidate': 5, 'mode': 'passive',
            'upstream': '3.8.0, unchanged; explicit review only', 'workspace': str(root),
            'registered_sources': len(sources), 'last_capture': max((s['seen_at'] for s in sources), default=None),
            'pending_batches': pending, 'pending_installs': installs,
            'review': startup.review_state(root, dt.date.today()),
            'coverage': 'Recorded Code/Cowork conversations and explicitly supplied artifacts only. '
                        'Hook-disabled/stateless inner calls are not fully observed. A capture is not a reviewed finding.',
            'scheduler': 'none installed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    subs.add_parser('capture')
    subs.add_parser('status')
    subs.add_parser('context')
    subs.add_parser('demo')
    p = subs.add_parser('harvest')
    p.add_argument('--source', action='append')
    p.add_argument('--days', type=int, default=7)
    p.add_argument('--max-bytes', type=int, default=400000)
    p = subs.add_parser('register-target')
    p.add_argument('--name', required=True)
    p.add_argument('--config', type=Path, required=True)
    p = subs.add_parser('freeze')
    p.add_argument('--batch', required=True)
    p.add_argument('--changes', type=Path, required=True)
    p = subs.add_parser('apply')
    p.add_argument('--batch', required=True)
    p.add_argument('--plan-hash', required=True)
    p = subs.add_parser('recover')
    p.add_argument('--batch', required=True)
    p.add_argument('--plan-hash', required=True)
    p = subs.add_parser('finish')
    p.add_argument('--batch', required=True)
    args = parser.parse_args()
    if args.command == 'capture':
        try:
            event = json.loads(sys.stdin.read() or '{}')
            if event.get('permission_mode') == 'plan':
                return 0
            root = workspace(create=event.get('hook_event_name') == 'SessionStart')
            capture(root, event)
        except Exception as e:
            print('Task Observer capture incomplete: ' + str(e), file=sys.stderr)
        return 0  # No decision, injected protocol, model call or ordinary-work gate.
    try:
        root = workspace(create=args.command in ['context', 'harvest', 'register-target', 'demo'])
        if args.command == 'status':
            result = status(root)
        elif args.command == 'context':
            result = {'workspace': str(root), 'original_skill': str(skill()),
                      'review_reference': str(skill() / 'references/weekly-review.md'),
                      'integration_guide': str(ROOT / 'integration/WORKFLOW.md'), 'status': status(root)}
        elif args.command == 'demo':
            result = prepare_demo(root)
        elif args.command == 'harvest':
            if args.max_bytes <= 0 or args.days < 1:
                raise ValueError('days and max-bytes must be positive')
            result = harvest(root, args.source, args.days, args.max_bytes)
        elif args.command == 'register-target':
            result = register(root, args.name, read_json(args.config))
        elif args.command == 'freeze':
            result = make_plan(root, args.batch, read_json(args.changes))
        elif args.command == 'apply':
            result = apply(root, args.batch, args.plan_hash)
        elif args.command == 'recover':
            result = recover(root, args.batch, args.plan_hash)
        else:
            result = finish_batch(root, args.batch)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except Exception as e:
        print(json.dumps({'state': 'pending', 'error': str(e),
                          'ordinary_work': 'unaffected; no observer gate is installed'}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
