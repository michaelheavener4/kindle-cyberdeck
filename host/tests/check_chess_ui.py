"""Run manually on the Kindle. No API calls, screenshot capture, or real moves."""
import json
import runpy
import sys
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

module = runpy.run_path('/usr/local/bin/deck-chess', run_name='chess_ui')
namespace = module['main'].__globals__
namespace['load_token'] = lambda: ''
namespace['_focus_legacy_instance'] = lambda: False
namespace['APPLICATION_ID'] = 'org.cyberdeck.Chess.Check'
namespace['choose_move'] = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('Online engine invoked'))
results = []


def settle():
    for _ in range(40):
        if Gtk.events_pending():Gtk.main_iteration_do(False)


def check():
    win = next(w for w in Gtk.Window.list_toplevels() if w.__class__.__name__ == 'Chess')
    assert win.lichess and win.asking_token
    outer = win.get_child()
    win.hide()
    win.remove(outer)
    screen = Gtk.OffscreenWindow()
    screen.add(outer)
    for width, height in [(1272,1584),(1696,1160),(1696,779),(1272,1076)]:
        for state in ['login','lobby','game','promotion']:
            win.asking_token = state == 'login'
            win.username = '' if state == 'login' else 'KindleTest'
            win.game_id = 'testgame' if state in ('game','promotion') else ''
            win.status_name = 'started' if win.game_id else ''
            win.connected_game = True
            win.promo = (48,56,'') if state == 'promotion' else None
            screen.set_default_size(width,height)
            screen.resize(width,height)
            screen.show_all()
            win.local_row.hide();win.mode_row.hide();win.lichess_button.hide()
            win.refresh()
            settle()
            rect = Gdk.Rectangle()
            rect.x=24;rect.y=28;rect.width=width-48;rect.height=height-52
            outer.size_allocate(rect)
            allocation=outer.get_allocation()
            bottom=win.live_footer.translate_coordinates(outer,0,win.live_footer.get_allocated_height())[1]
            assert bottom<=allocation.height, (width,height,state,bottom,allocation.height)
            results.append(dict(size=[width,height],state=state,actual=[allocation.width,allocation.height],
                board=[win.board.get_allocated_width(),win.board.get_allocated_height()]))
    # Validate authoritative game state + black orientation and human-only input.
    win.asking_token=False
    win.username='KindleTest'
    win._apply_full(dict(type='gameFull',white={'name':'Opponent'},black={'name':'KindleTest'},
        initialFen='startpos',state={'moves':'e2e4','status':'started','wtime':900000,'btime':900000}))
    assert win.my_color=='b' and win.mode=='b' and win.human_turn()
    win.on_square(namespace['parse_sq']('e7'))
    assert namespace['parse_sq']('e5') in win.targets
    win._maybe_engine()
    win._disconnected('testgame',win.session)
    assert not win.human_turn()
    screen.destroy();win.disconnect_by_func(Gtk.main_quit);win.destroy()
    print(json.dumps(results))


Gtk.main = check
sys.argv = ['deck-chess','--lichess']
module['main']()
