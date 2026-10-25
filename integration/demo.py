"""Create an explicitly synthetic, private, end-to-end live acceptance target."""
import json
from pathlib import Path
import shutil
import sys
import uuid

from common import now, private_dir, run, state, write_json
from installer import register


def prepare_demo(root):
    directory = private_dir(state(root) / 'demos' / uuid.uuid4().hex[:12])
    repo = private_dir(directory / 'source')
    run(['git', 'init', '-b', 'main'], repo)
    run(['git', 'config', 'user.name', 'Observer synthetic demo'], repo)
    run(['git', 'config', 'user.email', 'observer-demo@example.test'], repo)
    target = repo / 'skills/example-reply'
    target.mkdir(parents=True)
    (target / 'SKILL.md').write_text('---\nname: example-reply\ndescription: Synthetic demo reply skill; never install in real discovery\n---\n\nWrite a concise workplace reply. Prefer contractions such as I am -> I\'m.\n')
    (repo / 'README.md').write_text('# SYNTHETIC OBSERVER TEST TARGET\n\nNot a production skill or a user preference record.\n')
    (repo / '.gitignore').write_text('/dist/\n')
    (repo / 'validate.py').write_text("from pathlib import Path\np=Path('skills/example-reply/SKILL.md')\ns=p.read_text()\nassert 'name: example-reply' in s and 'description:' in s\nassert len(s.splitlines()) < 80\n")
    (repo / 'package.py').write_text("from pathlib import Path\nfrom zipfile import ZipFile\nimport json\nPath('dist').mkdir(exist_ok=True)\nwith ZipFile('dist/demo-plugin.zip','w') as z:\n z.write('skills/example-reply/SKILL.md','skills/example-reply/SKILL.md')\n z.writestr('.claude-plugin/plugin.json',json.dumps({'name':'observer-demo','version':'0.0.0','description':'Synthetic acceptance fixture; do not install'}))\n")
    run(['git', 'add', '.'], repo)
    run(['git', 'commit', '-m', 'test: synthetic observer acceptance baseline'], repo)
    remote = directory / 'remote.git'
    run(['git', 'init', '--bare', str(remote)])
    run(['git', 'remote', 'add', 'origin', str(remote)], repo)
    install = directory / 'installed-example-reply'
    shutil.copytree(target, install)
    source = directory / 'synthetic-session.jsonl'
    messages = [
        {'type': 'assistant', 'uuid': 'demo-tool-' + directory.name, 'message': {'content': [
            {'type': 'tool_use', 'id': 'demo-skill-call', 'name': 'Skill', 'input': {'skill': 'example-reply'}}]}},
        {'type': 'assistant', 'uuid': 'demo-draft-' + directory.name, 'message': {'content': "I'm checking the scope and I'll share what I find."}},
        {'type': 'user', 'uuid': 'demo-correction-' + directory.name, 'message': {'content': 'SYNTHETIC TEST CORRECTION: In this demo reply skill, use full English forms such as I am and I will instead of contractions.'}},
        {'type': 'assistant', 'uuid': 'demo-reply-' + directory.name, 'message': {'content': 'I am checking the scope and I will share what I find.'}},
    ]
    source.write_text(''.join(json.dumps(m) + '\n' for m in messages))
    name = 'demo-' + directory.name
    config = {'ownership': 'user', 'repo': str(repo), 'skill_dir': 'skills/example-reply',
              'installs': [str(install)], 'checks': [[sys.executable, 'validate.py']],
              'build': [[sys.executable, 'package.py']], 'artifacts': ['dist/demo-plugin.zip'],
              'publish': {'remote': 'origin', 'branch': 'main'}}
    register(root, name, config)
    result = {'synthetic': True, 'target': name, 'source': str(source), 'repo': str(repo),
              'installed_copy': str(install), 'remote': str(remote),
              'warning': 'No real skill, GitHub remote or discovery entry. Do not add synthetic findings to the production observation log/principles/review date.',
              'next': 'Harvest only this source; independently infer the change from the correction and show a staged diff.'}
    write_json(directory / 'DEMO.json', result)
    return result
