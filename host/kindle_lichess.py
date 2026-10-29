"""Private Lichess PKCE login bridge. Chess runs directly on the Kindle."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import threading
import time
import urllib.parse as U
import urllib.request as R

CLIENT = 'kindle-cyberdeck-native'
CALLBACK = 'http://127.0.0.1:8765/lichess/callback'
SCOPES = 'board:play'
KINDLE = 'root@kindle.example.invalid'
REMOTE = '/home/alpine/.config/kindle-chess/lichess.token'


def atomic_private(path, data):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as handle:
            handle.write(data)
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        temporary.unlink(missing_ok=True)


def api(path, token='', fields=None):
    headers = {'Accept': 'application/json', 'User-Agent': CLIENT}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    data = None if fields is None else U.urlencode(fields).encode()
    req = R.Request('https://lichess.org' + path, data=data, headers=headers)
    with R.urlopen(req, timeout=25) as response:
        return json.loads(response.read(65536))


class Login:
    def __init__(self, state):
        self.path = Path(state) / 'lichess-account.json'
        self.pending = {}
        self.lock = threading.Lock()

    def begin(self):
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        with self.lock:
            self.pending = {key: value for key, value in self.pending.items() if value[1] > time.monotonic()}
            self.pending[state] = (verifier, time.monotonic() + 900)
        return 'https://lichess.org/oauth?' + U.urlencode(dict(
            response_type='code', client_id=CLIENT, redirect_uri=CALLBACK,
            code_challenge_method='S256', code_challenge=challenge,
            scope=SCOPES, state=state))

    def complete(self, state, code, error=''):
        with self.lock:
            pending = self.pending.pop(state, None)
        if not pending or pending[1] < time.monotonic():
            raise ValueError('This sign-in link expired or was already used. Start again.')
        if error:
            raise ValueError('Lichess sign-in was cancelled. No account was connected.')
        if not re.fullmatch(r'[A-Za-z0-9_]{1,2048}', code):
            raise ValueError('Lichess did not return a valid authorization code.')
        result = api('/api/token', fields=dict(grant_type='authorization_code', code=code,
            code_verifier=pending[0], redirect_uri=CALLBACK, client_id=CLIENT))
        token = result.get('access_token', '')
        if not re.fullmatch(r'[A-Za-z0-9_]{1,2048}', token):
            raise ValueError('Lichess did not return an access token.')
        account = api('/api/account', token)
        name = account.get('username') or account.get('id')
        if not isinstance(name, str) or not name:
            raise ValueError('Could not verify the Lichess account.')
        atomic_private(self.path, json.dumps(dict(token=token, username=name, scope=SCOPES)))
        return name

    def saved(self):
        try:
            return json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}

    def deliver(self):
        account = self.saved()
        token = account.get('token', '')
        if not re.fullmatch(r'[A-Za-z0-9_]{1,2048}', token):
            raise ValueError('Sign in with Lichess first.')
        # Credential is passed over encrypted stdin, never in arguments or logs.
        script = ('import os,sys; p="' + REMOTE + '"; '
                  'os.makedirs(os.path.dirname(p),mode=0o700,exist_ok=True); '
                  't=p+".tmp"; fd=os.open(t,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600); '
                  'os.fchmod(fd,0o600); os.write(fd,sys.stdin.buffer.read()); os.close(fd); '
                  'os.replace(t,p); os.chmod(p,0o600)')
        import shlex
        result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=7',
            KINDLE, 'python3 -c ' + shlex.quote(script)], input=token + '\n',
            text=True, capture_output=True, timeout=15)
        if result.returncode:
            raise ValueError('The account is saved safely. Open Linux on the Kindle, then tap Send login again.')
        return account['username']
