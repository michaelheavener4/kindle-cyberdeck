import importlib.machinery
import importlib.util
import ast
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch,Mock

BIN=Path(__file__).resolve().parents[2]/'overlay/usr/local/bin'


def load(name,path):
    loader=importlib.machinery.SourceFileLoader(name,str(path))
    spec=importlib.util.spec_from_loader(loader.name,loader);module=importlib.util.module_from_spec(spec)
    loader.exec_module(module);return module


probe=load('instrument_probe_test',BIN/'deck-instrument-probe')
panel=load('instrument_panel_test',BIN/'deck-instruments')


class ProbeTests(unittest.TestCase):
    def test_linux_available_memory_and_mac_page_sizes(self):
        result=probe.linux_memory('MemTotal: 1000 kB\nMemAvailable: 250 kB\n')
        self.assertEqual(result,{'total':1024000,'used':768000})
        mac=probe.mac_memory(1024*1024,'Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free: 2.\nPages inactive: 3.\nPages speculative: 1.\n')
        self.assertEqual(mac['used'],1024*1024-6*16384)
        self.assertIsNone(probe.mac_memory(1024,'bad response'))
        self.assertIsNone(probe.linux_memory('MemTotal: nope'))

    def test_process_watch_never_returns_unrelated_process_information(self):
        self.assertEqual(probe.process_watch(['/usr/local/bin/codex','codex','/Applications/Cyberpunk2077','secret-file','bash']),
            [{'name':'Codex','count':2},{'name':'Cyberpunk','count':1}])

    def test_model_probe_only_reads_loaded_models(self):
        response=io.BytesIO(b'{"models":[{"name":"kindle-chat"}]}')
        with patch.object(probe.urllib.request,'urlopen',return_value=response) as call:
            self.assertEqual(probe.models(),{'available':True,'loaded':['kindle-chat']})
        self.assertEqual(call.call_args.args[0].full_url,'http://127.0.0.1:11434/api/ps')
        self.assertIsNone(call.call_args.args[0].data)

    def test_sessions_validate_fields_and_keep_state(self):
        self.assertEqual(probe.sessions('codex\t1\t2\ninvalid\tx\t0\nidle\t0\t1'),
            [{'name':'codex','attached':True,'windows':2},{'name':'idle','attached':False,'windows':1}])


class PanelTests(unittest.TestCase):
    def test_clock_uses_local_timezone_including_daylight_saving(self):
        with patch.object(panel,'CLOCK_TZ','America/Los_Angeles'):
            self.assertEqual(panel.clock_values(1767225600),('16:00','2025.12.31','PST'))
            self.assertEqual(panel.clock_values(1782864000)[2],'PDT')

    def test_automatic_reads_stop_when_paused_or_window_inactive(self):
        tree=ast.parse((BIN/'deck-instruments').read_text())
        method=next(node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='tick')
        clock=Mock();clock.monotonic.return_value=100
        scope={'INTERVAL':60,'time':clock}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'<tick>','exec'),scope)
        window=Mock();window.closed=False;window.paused=False;window.last_refresh=0
        window.window.get_property.return_value=False
        self.assertTrue(scope['tick'](window));window.refresh.assert_not_called()
        window.window.get_property.return_value=True;window.paused=True
        self.assertTrue(scope['tick'](window));window.refresh.assert_not_called()
        window.paused=False
        self.assertTrue(scope['tick'](window));window.refresh.assert_called_once()

    def test_collector_rejects_hosts_outside_the_three_machine_console(self):
        with patch.object(panel.subprocess,'Popen') as process:
            with self.assertRaises(ValueError):panel.Collector().remote('-oProxyCommand=anything')
            process.assert_not_called()

    def test_ssh_check_is_distinct_from_offline_and_never_leaks_url(self):
        state,message=panel.error_state('Tailscale SSH requires an additional check. To authenticate, visit: https://login.tailscale.com/a/private')
        self.assertEqual(state,'locked');self.assertNotIn('private',message)
        self.assertEqual(panel.error_state('connection timed out')[0],'offline')

    def test_failed_probe_preserves_and_marks_last_good_reading(self):
        old={'omarchy':{'state':'online','data':{'load':[1,2,3]},'received_at':100}}
        current={'omarchy':{'state':'offline','error':'No response'}}
        merged=panel.merge(old,current)
        self.assertEqual(merged['omarchy']['data'],old['omarchy']['data'])
        self.assertEqual(merged['omarchy']['received_at'],100)
        self.assertEqual(merged['omarchy']['state'],'offline')
        self.assertNotIn('data',current['omarchy'])

    def test_load_changes_do_not_flood_activity(self):
        old={'kindle':{'state':'online','data':{'load':[1,0,0],'sessions':[],'processes':[],'models':{}}}}
        new={'kindle':{'state':'online','data':{'load':[2,0,0],'sessions':[],'processes':[],'models':{}}}}
        self.assertEqual(panel.changes(old,new),[])
        new['kindle']['data']['sessions']=[{'name':'work'}]
        self.assertEqual(panel.changes(old,new),['KINDLE / SESSIONS CHANGED'])

    def test_diagram_hit_regions_fit_portrait_and_landscape(self):
        for width,height in [(1224,310),(1648,310),(700,310)]:
            for x,y,w,h in panel.positions(width,height).values():
                self.assertGreaterEqual(x,0);self.assertGreaterEqual(y,0)
                self.assertLessEqual(x+w,width);self.assertLessEqual(y+h,height)
                self.assertGreaterEqual(h,90)

    def test_remote_probe_uses_fixed_alias_and_no_model_execution(self):
        child=Mock();child.communicate.return_value=(json.dumps({'schema':1,'system':'Linux'}),'')
        child.returncode=0
        with patch.object(panel.subprocess,'Popen',return_value=child) as popen:
            result=panel.Collector().remote('omarchy')
        self.assertEqual(result['state'],'online')
        args=popen.call_args.args[0]
        self.assertEqual(args[-2],'omarchy');self.assertEqual(args[0],'ssh')
        self.assertIn('exec python3 -',args[-1]);self.assertNotIn('ollama run',args[-1])
        self.assertNotIn('fm chat',args[-1]);self.assertEqual(child.communicate.call_args.kwargs['timeout'],10)


if __name__=='__main__':unittest.main()
