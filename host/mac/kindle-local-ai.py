#!/usr/local/bin/python3
"""Mac-side AI entry points. Setup creates metadata aliases, never pulls/loads weights."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request

ROOT = Path.home() / '.local/share/kindle-ai'
API = 'http://127.0.0.1:11434'
MODELS = {
    'kindle-chat': ('huihui_ai/qwen3-abliterated:8b', 4096),
    'kindle-code': ('huihui_ai/qwen3-abliterated:8b', 16384),
    'kindle-code-large': ('richardyoung/qwen2.5-coder-14b-instruct-abliterated:latest', 8192),
}


def api(path, data=None, timeout=15):
    body = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(API + path, data=body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def gaming():
    value = subprocess.check_output(['/bin/ps', '-axo', 'comm'], text=True)
    return any(Path(line.strip()).name.lower() == 'cyberpunk2077' for line in value.splitlines())


def setup():
    ROOT.mkdir(parents=True, exist_ok=True)
    names = {m['name'] for m in api('/api/tags')['models']}
    for name, (base, context) in MODELS.items():
        if base not in names:
            raise RuntimeError('Base model is not installed: ' + base + '. No download was started.')
        result = api('/api/create', {'model': name, 'from': base, 'stream': False,
                    'parameters': {'num_ctx': context, 'num_predict': 2048}}, timeout=90)
        if result.get('status') != 'success':
            raise RuntimeError(str(result))
    config = {
        '$schema': 'https://opencode.ai/config.json',
        'enabled_providers': ['kindle-ollama'],
        'model': 'kindle-ollama/kindle-code',
        'provider': {'kindle-ollama': {
            'npm': '@ai-sdk/openai-compatible', 'name': 'Mac local models',
            'options': {'baseURL': API + '/v1'},
            'models': {
                'kindle-code': {'name': 'Local 8B coder', 'limit': {'context': 16384, 'output': 2048}},
                'kindle-code-large': {'name': 'Local 14B coder', 'limit': {'context': 8192, 'output': 2048}},
            },
        }},
    }
    (ROOT / 'opencode.json').write_text(json.dumps(config, indent=2))
    print(json.dumps({'profiles': list(MODELS), 'loaded_models': api('/api/ps')['models'], 'gaming': gaming()}))


def respond(request):
    provider = request.get('provider', 'fm')
    messages = request.get('messages', [])[-6:]
    if not messages or any(m.get('role') not in {'user', 'assistant'} or not isinstance(m.get('content'), str) for m in messages):
        raise ValueError('Invalid conversation.')
    if provider == 'fm':
        prompt = '\n\n'.join(m['role'].upper() + ': ' + m['content'][-2500:] for m in messages)[-12000:]
        prompt += '\n\nASSISTANT:'
        env = os.environ.copy(); env['NO_COLOR'] = '1'
        result = subprocess.run(['/usr/bin/fm', 'respond', '--no-stream', '--instructions',
            'Answer the user helpfully and clearly. Be concise unless asked for detail.', prompt],
            env=env, capture_output=True, text=True, timeout=180)
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout)[-1500:].strip())
        answer = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', result.stdout).strip()
    elif provider == 'ollama':
        if gaming():
            raise RuntimeError('Cyberpunk is running. Use Apple FM now, or use Ollama after closing the game.')
        result = api('/api/chat', {'model': 'kindle-chat', 'messages': messages, 'stream': False,
                     'think': False, 'keep_alive': '30s', 'options': {'num_ctx': 4096, 'num_predict': 1024}}, timeout=240)
        answer = result['message']['content']
    else:
        raise ValueError('Unknown model provider.')
    return {'reply': answer}


def status():
    installed = api('/api/tags')['models']
    return {'gaming': gaming(), 'profiles': [m['name'] for m in installed if m['name'].startswith('kindle-')],
            'loaded': [m['name'] for m in api('/api/ps')['models']]}


def terminal():
    ollama = shutil.which('ollama') or '/usr/local/bin/ollama'
    while True:
        print('\nMAC LOCAL AI\n\n1  Chat - abliterated 8B\n2  Coding agent - 8B\n3  Coding chat - 14B (more memory)\n4  Installed models / status\n0  Back')
        choice = input('\nChoice: ').strip()
        if choice == '0': return
        if choice == '4':
            print(json.dumps(status(), indent=2)); continue
        if choice not in {'1', '2', '3'}: continue
        if gaming():
            print('Cyberpunk is running. Local model loading is deferred until the game is closed.')
            continue
        model = {'1': 'kindle-chat', '2': 'kindle-code', '3': 'kindle-code-large'}[choice]
        try:
            if choice == '2':
                folder = input('Project directory [~/Projects/kindle-workspace]: ').strip() or '~/Projects/kindle-workspace'
                folder = Path(folder).expanduser()
                folder.mkdir(parents=True, exist_ok=True)
                env = os.environ.copy(); env['OPENCODE_CONFIG'] = str(ROOT / 'opencode.json')
                subprocess.run(['opencode', '--model', 'kindle-ollama/kindle-code', str(folder)], env=env)
            else:
                subprocess.run([ollama, 'run', model])
        finally:
            subprocess.run([ollama, 'stop', model], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--setup', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--respond', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.setup: setup()
        elif args.status: print(json.dumps(status()))
        elif args.respond: print(json.dumps(respond(json.load(sys.stdin))))
        else: terminal()
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        if args.respond: print(json.dumps({'error': str(exc)}))
        else: print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
