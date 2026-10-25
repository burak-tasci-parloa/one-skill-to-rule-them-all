#!/usr/bin/env python3
"""Optional real-CLI probe with a LOCAL FAKE model, fake HOME and no user data.

This proves plugin discovery/hook wiring, not real model judgment or human approval.
Usage: python3 tests/probe_claude_runtime.py /absolute/claude /absolute/plugin-dir
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading


def probe(binary, plugin):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers.get('content-length', '0'))))
            requests.append(data)
            value = {'id': 'msg_synthetic_local_probe', 'type': 'message', 'role': 'assistant',
                     'model': data.get('model', 'fixture'), 'content': [{'type': 'text', 'text': 'READY'}],
                     'stop_reason': 'end_turn', 'stop_sequence': None,
                     'usage': {'input_tokens': 1, 'output_tokens': 1}}
            payload = json.dumps(value).encode()
            self.send_response(200)
            self.send_header('content-type', 'application/json')
            self.send_header('content-length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix='observer-real-cli-fake-model-') as temp:
            home = (Path(temp) / 'home').resolve()
            cwd = home / 'project'
            cwd.mkdir(parents=True)
            env = {k: os.environ[k] for k in ['PATH', 'TMPDIR', 'LANG', 'SHELL'] if k in os.environ}
            env.update(HOME=str(home), CLAUDE_CONFIG_DIR=str(home / '.claude'),
                       TASK_OBSERVER_WORKSPACE=str(home / 'Developer/task-observer'),
                       ANTHROPIC_API_KEY='synthetic-local-probe-not-a-real-key',
                       ANTHROPIC_BASE_URL='http://127.0.0.1:' + str(server.server_port),
                       CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1', DISABLE_TELEMETRY='1')
            command = [str(binary), '-p', 'Reply only READY', '--model', 'claude-sonnet-4-5',
                       '--output-format', 'stream-json', '--verbose', '--max-turns', '1',
                       '--plugin-dir', str(plugin), '--setting-sources', '']
            result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, timeout=40)
            events = []
            for line in result.stdout.splitlines():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    pass
            init = next((e for e in events if e.get('type') == 'system' and e.get('subtype') == 'init'), {})
            names = init.get('slash_commands', [])
            expected = 'task-observer:task-observer'
            assert expected in names, {'missing_skill': expected, 'stderr': result.stderr[-2000:]}
            assert not any(name.startswith('task-observer:') and name != expected for name in names), names
            assert result.returncode == 0, {'code': result.returncode, 'stderr': result.stderr[-2000:]}
            assert requests, 'no local fake-model request received'
            serialized = json.dumps(requests)
            assert 'Load the registered ORIGINAL task-observer skill' in serialized, 'startup context missing'
            assert 'Monitors task execution for skill improvement' in serialized, 'original skill metadata missing'
            pool = home / 'Developer/task-observer'
            assert (pool / 'skill-observations/observation-log').is_dir(), 'bootstrap did not run'
            assert not (pool / 'skill-observations/.plugin').exists(), 'old collection state was created'
            return {'runtime': init.get('claude_code_version'), 'skill_discovered': expected,
                    'extra_observer_commands': [], 'startup_context_delivered': True,
                    'workspace_initialized': True, 'model': 'local fake HTTP server; no real model/API billing',
                    'actual_model_skill_invocation_tested': False, 'human_approval_tested': False,
                    'real_model_review_tested': False}
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    print(json.dumps(probe(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()), indent=2))
