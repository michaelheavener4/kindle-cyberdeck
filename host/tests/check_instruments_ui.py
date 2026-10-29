"""Isolated native GTK check; no real SSH, models, screenshots or tool launches."""
import copy
import json
from pathlib import Path
import runpy
import sys
import tempfile
import time
from types import SimpleNamespace
import gi
gi.require_version('Gtk','3.0');gi.require_version('Gdk','3.0')
from gi.repository import Gtk,Gdk

module=runpy.run_path('/usr/local/bin/deck-instruments',run_name='instrument_ui_check')
namespace=module['main'].__globals__
temporary=tempfile.TemporaryDirectory()
namespace['CACHE']=Path(temporary.name)/'snapshot.json'
namespace['APPLICATION_ID']='org.cyberdeck.Instruments.Check'
fixture={'schema':1,'cores':4,'load':[0.42,0.31,0.25],'memory':{'used':400000000,'total':1000000000},
         'uptime':12400,'storage':{'total':16000000000,'used':4000000000},'processes':[{'name':'Codex','count':1}],
         'sessions':[{'name':'kindle','attached':True,'windows':1},{'name':'codex','attached':False,'windows':2}],
         'models':{'available':True,'loaded':['kindle-chat']}}
nodes={key:{'state':'online','data':copy.deepcopy(fixture),'received_at':time.time(),'probe_ms':200}
       for key in ('kindle','omarchy')}
nodes['mac']={'state':'offline','error':'No response.'}


class FakeCollector:
    calls=0
    def collect(self):self.calls+=1;return nodes
    def stop(self):pass


namespace['Collector']=FakeCollector
real_run=Gtk.Application.run


def settle():
    until=time.monotonic()+0.15
    while time.monotonic()<until:
        if Gtk.events_pending():Gtk.main_iteration_do(False)
        else:time.sleep(0.003)


def check(application,_args):
    application.register(None);application.activate();settle()
    application.received(copy.deepcopy(nodes),None)
    assert application.nodes['omarchy']['state']=='online'
    assert '400' not in application.memory_label.get_text() # percentage, not an unlabelled byte count
    window=application.window;outer=window.get_child();window.hide();window.remove(outer)
    screen=Gtk.OffscreenWindow();screen.add(outer)
    results=[]
    for width,height in [(1272,1584),(1696,1160),(1696,779),(1272,1076)]:
        screen.set_default_size(width,height);screen.resize(width,height);screen.show_all();settle()
        for node in ('kindle','omarchy','mac'):
            application.select(node);settle()
            rect=Gdk.Rectangle();rect.x=0;rect.y=0;rect.width=width;rect.height=height
            outer.size_allocate(rect)
            footer=application.refresh_button.get_parent()
            bottom=footer.translate_coordinates(outer,0,footer.get_allocated_height())[1]
            assert bottom<=outer.get_allocated_height(),(width,height,node,'footer clipped')
            scroll=outer.get_children()[2]
            assert scroll.get_allocated_height()>120,(width,height,node,'no scrolling space')
            results.append({'size':[width,height],'node':node,'footer_bottom':bottom,
                'viewport_height':scroll.get_allocated_height()})
    application.select('omarchy');commands=[];application.launch=commands.append
    next(button for button in application.actions.get_children() if button.get_label()=='SHELL').clicked()
    assert commands[-1][-3:]==['deck-connect','omarchy','kindle']
    application.network.buttons['mac'].clicked()
    assert application.selected=='mac' and 'OFFLINE' in application.detail.get_text()
    application.network.buttons['kindle'].clicked();assert application.selected=='kindle'
    application.network.buttons['omarchy'].clicked();assert application.selected=='omarchy'
    assert len(application.clock.stamp[0])==5
    application.toggle_pause();calls=application.collector.calls
    application.tick();assert application.collector.calls==calls
    assert application.paused
    screen.destroy();window.destroy();application.quit()
    print(json.dumps({'ok':True,'layouts':results,'tap_and_shell_controls':True,'pause':True}))
    return 0


Gtk.Application.run=check
try:module['main']()
finally:Gtk.Application.run=real_run;temporary.cleanup()
