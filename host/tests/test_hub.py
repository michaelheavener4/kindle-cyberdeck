import importlib.util,importlib.machinery,json,tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch

def module(name,path):
    loader=importlib.machinery.SourceFileLoader(name,str(path));spec=importlib.util.spec_from_loader(name,loader);m=importlib.util.module_from_spec(spec);loader.exec_module(m);return m
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'host'))
h=module('hub',root/'host/kindle-hub');mac=module('mac_ai',root/'host/mac/kindle-local-ai.py')
class Tests(unittest.TestCase):
 def setUp(self):
    self.tmp=tempfile.TemporaryDirectory();h.STATE=Path(self.tmp.name);h.init()
 def tearDown(self):self.tmp.cleanup()
 def test_escaped_chat_and_reply(self):
    with h.db() as c:
     c.execute('INSERT INTO chats VALUES(?,?,?,?)',('test','<script>','fm',1))
     c.execute('INSERT INTO messages(chat_id,role,content,status) VALUES(?,?,?,?)',('test','user','<img src=x>','done'))
     mid=c.execute('INSERT INTO messages(chat_id,role,content,status) VALUES(?,?,?,?)',('test','assistant','','pending')).lastrowid
    fake=type('Result',(),{'stdout':json.dumps({'reply':'Answer <safe>'})})()
    with patch.object(h.subprocess,'run',return_value=fake) as run:h.answer('test',mid)
    self.assertEqual(json.loads(run.call_args.kwargs['input'])['messages'],[{'role':'user','content':'<img src=x>'}])
    page=h.chat_page('test');self.assertIn('&lt;img src=x&gt;',page);self.assertIn('Answer &lt;safe&gt;',page);self.assertNotIn('<script>',page)
 def test_archive_search_escape(self):
    data={'response':{'numFound':1,'docs':[{'identifier':'valid','title':'<unsafe>','creator':['A','B'],'mediatype':'texts'}]}}
    with patch.object(h,'fetch',return_value=json.dumps(data).encode()):page=h.archive_search('hello','texts')
    self.assertIn('&lt;unsafe&gt;',page);self.assertIn('/archive/item/valid',page)
 def test_archive_identifiers(self):
    for value in ['../secret','/etc/passwd','bad?foo','']:
     with self.assertRaises(ValueError):h.item_id(value)
 def test_game_guard_never_calls_model(self):
    with patch.object(mac,'gaming',return_value=True),patch.object(mac,'api') as api:
     with self.assertRaisesRegex(RuntimeError,'Cyberpunk'):mac.respond({'provider':'ollama','messages':[{'role':'user','content':'hello'}]})
     api.assert_not_called()
 def test_fm_request(self):
    result=type('Result',(),{'returncode':0,'stdout':'An answer','stderr':''})()
    with patch.object(mac.subprocess,'run',return_value=result) as run:
     self.assertEqual(mac.respond({'provider':'fm','messages':[{'role':'user','content':'hello'}]}),{'reply':'An answer'})
     self.assertIn('--no-stream',run.call_args.args[0])
if __name__ == "__main__": unittest.main()
