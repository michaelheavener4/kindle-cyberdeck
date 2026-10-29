import importlib.machinery
import importlib.util
import io
import ast
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse as U

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'host'))
import kindle_lichess as login

loader = importlib.machinery.SourceFileLoader('deck_chess', str(ROOT / 'overlay/usr/local/bin/deck-chess'))
spec = importlib.util.spec_from_loader(loader.name, loader)
chess = importlib.util.module_from_spec(spec)
loader.exec_module(chess)


class LoginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.login = login.Login(self.tmp.name)

    def begin(self):
        return {k: v[0] for k, v in U.parse_qs(U.urlsplit(self.login.begin()).query).items()}

    def test_pkce_state_is_single_use_and_private(self):
        query = self.begin()
        self.assertEqual(query['scope'], 'board:play')
        self.assertEqual(query['code_challenge_method'], 'S256')
        self.assertNotIn(self.login.pending[query['state']][0], json.dumps(query))
        with patch.object(login, 'api', side_effect=[{'access_token': 'lip_secret'}, {'username': 'Player'}]) as api:
            self.assertEqual(self.login.complete(query['state'], 'liu_code'), 'Player')
            self.assertEqual(api.call_args_list[0].kwargs['fields']['redirect_uri'], login.CALLBACK)
        self.assertEqual(self.login.path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(ValueError):
            self.login.complete(query['state'], 'liu_code')

    def test_bad_state_denial_and_expiry_never_exchange(self):
        query = self.begin()
        with patch.object(login, 'api') as api:
            for state, error in [('wrong', ''), (query['state'], 'access_denied')]:
                with self.assertRaises(ValueError):self.login.complete(state, 'code', error)
            query = self.begin()
            self.login.pending[query['state']] = ('verifier', time.monotonic() - 1)
            with self.assertRaises(ValueError):self.login.complete(query['state'], 'code')
            api.assert_not_called()
        self.assertFalse(self.login.path.exists())

    def test_delivery_keeps_secret_out_of_command_line(self):
        login.atomic_private(self.login.path, json.dumps({'token': 'lip_secret', 'username': 'Player'}))
        with patch.object(login.subprocess, 'run') as run:
            run.return_value.returncode = 0
            self.assertEqual(self.login.deliver(), 'Player')
            self.assertNotIn('lip_secret', ' '.join(run.call_args.args[0]))
            self.assertEqual(run.call_args.kwargs['input'], 'lip_secret\n')
            run.return_value.returncode = 255
            with self.assertRaisesRegex(ValueError, 'Open Linux'):self.login.deliver()


class BoardTests(unittest.TestCase):
    def test_existing_board_is_focused_instead_of_duplicated(self):
        from unittest.mock import mock_open, Mock
        cmdline = b'/usr/bin/python3\0' + str(ROOT / 'overlay/usr/local/bin/deck-chess').encode() + b'\0--lichess\0'
        with patch.object(chess.os, 'listdir', return_value=['12345']), \
             patch('builtins.open', mock_open(read_data=cmdline)), \
             patch.object(chess.subprocess, 'run', return_value=Mock(stdout='9876\n')) as run:
            self.assertTrue(chess._focus_legacy_instance())
        self.assertEqual(run.call_args_list[-1].args[0], ['xdotool','windowactivate','9876'])

    def test_username_typing_does_not_activate_board_shortcuts(self):
        tree = ast.parse((ROOT / 'overlay/usr/local/bin/deck-chess').read_text())
        key = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == '_key')
        entry_type = type('Entry', (), {})
        from unittest.mock import Mock
        gdk = Mock()
        scope = {'Gtk': type('Gtk', (), {'Entry': entry_type}), 'Gdk': gdk}
        exec(compile(ast.Module(body=[key], type_ignores=[]), '<key-handler>', 'exec'), scope)
        window = Mock()
        window.get_focus.return_value = entry_type()
        self.assertFalse(scope['_key'](window, None, Mock()))
        gdk.keyval_name.assert_not_called()
        window.destroy.assert_not_called()

    def test_stream_blank_lines_and_bad_json(self):
        response = io.BytesIO(b'\n{bad}\n{"type":"gameState","moves":"e2e4"}\n')
        client = chess.LichessClient('lip_secret')
        with patch.object(client, '_open_request', return_value=(200, '', response)):
            self.assertEqual(list(client.iter_stream('GET', '/test')), [('event', 200, {'type':'gameState','moves':'e2e4'})])
        self.assertTrue(response.closed)

    def test_rate_limit_stops_retries_and_closed_client_never_requests(self):
        self.addCleanup(setattr, chess.LichessClient, 'cooldown', 0.0)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        rate_file = str(Path(directory.name) / 'cooldown')
        patcher = patch.object(chess.LichessClient, 'rate_file', rate_file)
        patcher.start();self.addCleanup(patcher.stop)
        client = chess.LichessClient('lip_secret')
        error = urllib.error.HTTPError('https://lichess.org', 429, 'limit', {}, io.BytesIO(b'{}'))
        with patch.object(chess.urllib.request, 'urlopen', side_effect=error) as open_request:
            self.assertEqual(client.call('GET', '/api/account')[0], 429)
            self.assertEqual(client.call('POST', '/test')[0], 429)
            self.assertEqual(chess.LichessClient('lip_secret').call('GET', '/api/account')[0], 429)
            self.assertEqual(open_request.call_count, 1)
            chess.LichessClient.cooldown = 0
            self.assertEqual(chess.LichessClient('lip_secret').call('GET', '/api/account')[0], 429)
            client.close()
            self.assertEqual(client.call('GET', '/api/account')[0], 0)

    def test_move_legality_and_special_move_replay(self):
        self.assertIsNone(chess.replay_moves('startpos', 'e2e5'))
        game = chess.replay_moves('startpos', 'e2e4 e7e5 g1f3 b8c6 f1c4 f8c5 e1g1')
        self.assertEqual(game.board[chess.parse_sq('g1')], 'K')
        self.assertEqual(game.board[chess.parse_sq('f1')], 'R')
        for uci in ['e7e8q', 'e7e8n', 'e7e8r', 'e7e8b']:
            game = chess.replay_moves('k7/4P3/8/8/8/8/8/4K3 w - - 0 1', uci)
            self.assertEqual(game.board[chess.parse_sq('e8')], uci[-1].upper())

    def test_private_token_permissions_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory)/'token')
            chess.save_token('lip_test', path)
            self.assertEqual(chess.load_token(path), 'lip_test')
            self.assertEqual(Path(path).stat().st_mode & 0o777, 0o600)
        self.assertFalse(chess.token_ok('lip_é'))
        self.assertTrue(chess.token_ok('x'*1024))


if __name__ == '__main__':unittest.main()
