/* A small GTK3 touch front end for the existing NetSurf engine.
 * Uses public GTK/GDK ABI; built without installing a compiler on the Kindle.
 * Only GtkLayout page content is intercepted. Native entry editing is intact.
 */
typedef void W;
typedef unsigned long U;
typedef struct List { void *data; struct List *next, *prev; } List;
typedef void (*Handler)(void *, void *);
extern void *dlsym(void *, const char *);
extern int unsetenv(const char *);
extern void *g_object_ref(void *);
extern void g_object_unref(void *);
extern void *g_object_get_data(void *, const char *);
extern void g_object_set_data(void *, const char *, void *);
extern unsigned g_timeout_add(unsigned, int (*)(void *), void *);
extern U g_signal_connect_data(void *, const char *, void (*)(), void *, void *, int);
extern void g_signal_emit_by_name(void *, const char *, ...);
extern int g_type_check_instance_is_a(void *, U);
extern void g_list_free(List *);
extern void g_spawn_command_line_async(const char *, void *);
extern W *gtk_widget_get_parent(W *);
extern void gtk_widget_hide(W *);
extern void gtk_widget_show(W *);
extern void gtk_widget_show_all(W *);
extern void gtk_widget_set_no_show_all(W *, int);
extern void gtk_widget_set_name(W *, const char *);
extern void gtk_widget_set_can_focus(W *, int);
extern void gtk_widget_set_size_request(W *, int, int);
extern int gtk_widget_get_visible(W *);
extern int gtk_widget_get_sensitive(W *);
extern void gtk_widget_set_sensitive(W *, int);
extern void gtk_window_close(W *);
extern List *gtk_window_list_toplevels(void);
extern List *gtk_container_get_children(W *);
extern U gtk_container_get_type(void);
extern U gtk_box_get_type(void);
extern U gtk_layout_get_type(void);
extern U gtk_toolbar_get_type(void);
extern U gtk_tool_button_get_type(void);
extern U gtk_menu_bar_get_type(void);
extern U gtk_menu_item_get_type(void);
extern U gtk_entry_get_type(void);
extern W *gtk_menu_item_get_submenu(W *);
extern const char *gtk_menu_item_get_label(W *);
extern const char *gtk_tool_button_get_label(W *);
extern const char *gtk_tool_button_get_stock_id(W *);
extern void gtk_toolbar_set_show_arrow(W *, int);
extern W *gtk_box_new(int, int);
extern void gtk_box_set_homogeneous(W *, int);
extern void gtk_box_pack_start(W *, W *, int, int, unsigned);
extern void gtk_box_reorder_child(W *, W *, int);
extern W *gtk_button_new_with_label(const char *);
extern void gtk_button_set_label(W *, const char *);
extern void gtk_entry_set_text(W *, const char *);
extern W *gtk_layout_get_vadjustment(W *);
extern W *gtk_layout_get_hadjustment(W *);
extern double gtk_adjustment_get_value(W *);
extern double gtk_adjustment_get_page_size(W *);
extern void gtk_adjustment_set_value(W *, double);
extern W *gtk_css_provider_new(void);
extern int gtk_css_provider_load_from_data(W *, const char *, long, void *);
extern void gtk_style_context_add_provider_for_screen(W *, W *, unsigned);
extern W *gdk_screen_get_default(void);
extern int gdk_event_get_event_type(void *);
extern W *gdk_event_get_window(void *);
extern void gdk_window_get_user_data(W *, W **);
extern int gdk_event_get_button(void *, unsigned *);
extern int gdk_event_get_root_coords(void *, double *, double *);
extern void *gdk_event_copy(void *);
extern void gdk_event_free(void *);

typedef struct {
    W *window, *box, *layout, *entry, *back, *forward, *reload, *zin, *zout, *tools, *nav, *ui_back, *ui_forward;
} Browser;
static Browser browsers[12];
static Handler original;
static void *original_data;
static void *press;
static W *drag_widget;
static double start_x, start_y, last_x, last_y;
static int dragging, select_mode;
static unsigned long taps, swipes;

static int is(W *w, U type) { return w && g_type_check_instance_is_a(w, type); }
static int contains(const char *s, const char *word) {
    if (!s) return 0;
    for (; *s; ++s) {
        const char *a=s, *b=word;
        while (*a && *b) {
            char c=*a; if (c=='_') { ++a; continue; }
            if (c>='A' && c<='Z') c+=32;
            if (c!=*b) break;
            ++a; ++b;
        }
        if (!*b) return 1;
    }
    return 0;
}
static void clear_press(void) {
    if (press) gdk_event_free(press);
    if (drag_widget) g_object_unref(drag_widget);
    press=0; drag_widget=0; dragging=0;
}
static void move_adjustment(W *a, double delta) {
    if (a) gtk_adjustment_set_value(a, gtk_adjustment_get_value(a)+delta);
}
static W *page_widget(void *event) {
    W *w=0, *window=gdk_event_get_window(event);
    if (window) gdk_window_get_user_data(window, &w);
    while (w) {
        if (is(w, gtk_layout_get_type())) return w;
        w=gtk_widget_get_parent(w);
    }
    return 0;
}
static void events(void *event, void *unused) {
    (void)unused;
    int type=gdk_event_get_event_type(event);
    unsigned button=0;
    double x=0,y=0;
    if (select_mode) { if (original) original(event,original_data); return; }
    if (type==4 && gdk_event_get_button(event,&button) && button==1) {
        W *w=page_widget(event);
        if (w) {
            clear_press(); press=gdk_event_copy(event); drag_widget=g_object_ref(w);
            gdk_event_get_root_coords(event,&start_x,&start_y);
            last_x=start_x; last_y=start_y;
            return;
        }
    }
    if (type==3 && press) {
        gdk_event_get_root_coords(event,&x,&y);
        double dx=x-start_x,dy=y-start_y;
        if (!dragging && (dx*dx+dy*dy)>324) { dragging=1; ++swipes; }
        if (dragging) {
            move_adjustment(gtk_layout_get_vadjustment(drag_widget),last_y-y);
            move_adjustment(gtk_layout_get_hadjustment(drag_widget),last_x-x);
            last_x=x; last_y=y;
        }
        return;
    }
    if (type==7 && press && gdk_event_get_button(event,&button) && button==1) {
        if (!dragging && original) { ++taps; original(press,original_data); original(event,original_data); }
        clear_press(); return;
    }
    /* Suppress synthetic double/triple presses: tapping opens links once. */
    if ((type==5 || type==6) && page_widget(event)) return;
    if (original) original(event,original_data);
}
void gdk_event_handler_set(Handler func, void *data, void (*notify)(void *)) {
    typedef void (*Set)(Handler, void *, void (*)(void *));
    Set real=(Set)dlsym((void *)-1,"gdk_event_handler_set");
    original=func; original_data=data;
    /* GTK's handler data is NULL and has no destructor. Preserve non-GTK users. */
    if (notify) { real(func,data,notify); return; }
    real(events,0,0);
}
static void clicked(W *button, void *data) {
    Browser *b=(Browser *)data;
    const char *action=g_object_get_data(button,"deck-action");
    if (!b->window || !action) return;
    if (contains(action,"back") && b->back) g_signal_emit_by_name(b->back,"clicked");
    else if (contains(action,"forward") && b->forward) g_signal_emit_by_name(b->forward,"clicked");
    else if (contains(action,"reload") && b->reload) g_signal_emit_by_name(b->reload,"clicked");
    else if (contains(action,"home") && b->entry) {
        gtk_entry_set_text(b->entry,"http://127.0.0.1:8765/home"); g_signal_emit_by_name(b->entry,"activate");
    } else if (contains(action,"keys")) g_spawn_command_line_async("/usr/local/bin/kindle-keyboard toggle",0);
    else if (contains(action,"tools")) {
        if (gtk_widget_get_visible(b->tools)) gtk_widget_hide(b->tools); else gtk_widget_show(b->tools);
    } else if (contains(action,"select")) {
        clear_press(); select_mode=!select_mode;
        gtk_button_set_label(button,select_mode?"Select: on":"Swipe: on");
    } else if (contains(action,"up")) {
        W *a=gtk_layout_get_vadjustment(b->layout); move_adjustment(a,-gtk_adjustment_get_page_size(a)*0.8);
    } else if (contains(action,"down")) {
        W *a=gtk_layout_get_vadjustment(b->layout); move_adjustment(a,gtk_adjustment_get_page_size(a)*0.8);
    } else if (contains(action,"smaller") && b->zout) g_signal_emit_by_name(b->zout,"activate");
    else if (contains(action,"bigger") && b->zin) g_signal_emit_by_name(b->zin,"activate");
    else if (contains(action,"close")) gtk_window_close(b->window);
}
static W *add_button(Browser *b,W *row,const char *text,const char *action) {
    W *button=gtk_button_new_with_label(text);
    gtk_widget_set_can_focus(button,0);
    g_object_set_data(button,"deck-action",(void *)action);
    g_signal_connect_data(button,"clicked",(void (*)())clicked,b,0,0);
    gtk_box_pack_start(row,button,1,1,0);
    return button;
}
static W *find_type(W *w,U type) {
    if (is(w,type)) return w;
    if (is(w,gtk_container_get_type())) {
        List *list=gtk_container_get_children(w);
        W *found=0;
        for (List *p=list;p && !found;p=p->next) found=find_type(p->data,type);
        g_list_free(list); return found;
    }
    return 0;
}
static void inspect(W *w,Browser *b) {
    if (is(w,gtk_tool_button_get_type()) && gtk_widget_get_parent(w)==b->nav) {
        const char *label=gtk_tool_button_get_label(w), *stock=gtk_tool_button_get_stock_id(w);
        if (contains(label,"back") || contains(stock,"go-back")) b->back=w;
        if (contains(label,"forward") || contains(stock,"go-forward")) b->forward=w;
        if (contains(label,"reload") || contains(stock,"refresh")) b->reload=w;
    }
    if (is(w,gtk_menu_item_get_type())) {
        const char *label=gtk_menu_item_get_label(w);
        if (contains(label,"zoom in")) b->zin=w;
        if (contains(label,"zoom out")) b->zout=w;
        W *sub=gtk_menu_item_get_submenu(w); if (sub) inspect(sub,b);
    }
    if (is(w,gtk_toolbar_get_type())) {
        W *entry=find_type(w,gtk_entry_get_type());
        if (entry && !b->entry) {
            b->entry=entry; b->nav=w; gtk_toolbar_set_show_arrow(w,0);
            List *list=gtk_container_get_children(w);
            for (List *p=list;p;p=p->next) {
                W *child=p->data;
                if (!find_type(child,gtk_entry_get_type())) {
                    inspect(child,b); gtk_widget_hide(child); gtk_widget_set_no_show_all(child,1);
                }
            }
            g_list_free(list);
        }
    }
    if (is(w,gtk_menu_bar_get_type())) { gtk_widget_hide(w); gtk_widget_set_no_show_all(w,1); }
    if (is(w,gtk_container_get_type())) {
        List *list=gtk_container_get_children(w);
        for (List *p=list;p;p=p->next) inspect(p->data,b);
        g_list_free(list);
    }
}
static void destroyed(W *window, void *data) {
    (void)window;
    Browser *b=data;
    if (press && drag_widget==b->layout) clear_press();
    b->window=0;
}
static int install(void *unused) {
    (void)unused;
    List *list=gtk_window_list_toplevels();
    for (List *p=list;p;p=p->next) {
        W *window=p->data;
        Browser *existing=g_object_get_data(window,"deck-browser");
        if (existing) {
            if (existing->ui_back && existing->back) gtk_widget_set_sensitive(existing->ui_back,gtk_widget_get_sensitive(existing->back));
            if (existing->ui_forward && existing->forward) gtk_widget_set_sensitive(existing->ui_forward,gtk_widget_get_sensitive(existing->forward));
            continue;
        }
        W *layout=find_type(window,gtk_layout_get_type());
        W *box=find_type(window,gtk_box_get_type());
        if (!layout || !box) continue;
        Browser *b=0;
        for (int i=0;i<12;++i) if (!browsers[i].window) { b=&browsers[i]; break; }
        if (!b) continue;
        *b=(Browser){0}; b->window=window; b->box=box; b->layout=layout;
        g_object_set_data(window,"deck-browser",b);
        inspect(window,b);
        W *top=gtk_box_new(0,6), *tools=gtk_box_new(0,6);
        b->tools=tools; gtk_box_set_homogeneous(top,1); gtk_box_set_homogeneous(tools,1);
        b->ui_back=add_button(b,top,"Back","back"); b->ui_forward=add_button(b,top,"Forward","forward");
        add_button(b,top,"Home","home"); add_button(b,top,"Keys","keys"); add_button(b,top,"Tools","tools");
        add_button(b,tools,"Up","up"); add_button(b,tools,"Down","down");
        add_button(b,tools,"A -","smaller"); add_button(b,tools,"A +","bigger");
        add_button(b,tools,"Swipe: on","select"); add_button(b,tools,"Reload","reload");
        gtk_box_pack_start(box,top,0,1,0); gtk_box_reorder_child(box,top,0);
        gtk_box_pack_start(box,tools,0,1,0); gtk_box_reorder_child(box,tools,1);
        gtk_widget_show_all(top); gtk_widget_show_all(tools); gtk_widget_hide(tools);
        g_signal_connect_data(window,"destroy",(void (*)())destroyed,b,0,0);
    }
    g_list_free(list);
    return 1;
}
static int setup(void *unused) {
    (void)unused;
    W *screen=gdk_screen_get_default(); if (!screen) return 1;
    W *css=gtk_css_provider_new();
    const char *rules="* { font-family: 'DejaVu Sans'; font-size: 30px; } window { background: #fff; color: #111; } button { min-height: 62px; padding: 12px 8px; border: 3px solid #111; border-radius: 0; background: #fff; color: #111; } button:active { background:#111; color:#fff; } entry { min-height: 62px; padding: 8px; border: 3px solid #111; border-radius:0; } scrollbar slider { min-width: 48px; min-height: 48px; background:#444; border:2px solid #111; } menuitem { min-height:72px; padding:12px; }";
    gtk_css_provider_load_from_data(css,rules,-1,0);
    gtk_style_context_add_provider_for_screen(screen,css,600); g_object_unref(css);
    g_timeout_add(600,install,0); install(0);
    return 0;
}
__attribute__((constructor)) static void start(void) {
    /* Image-loader subprocesses are not GTK apps and must not inherit this. */
    unsetenv("LD_PRELOAD");
    g_timeout_add(150,setup,0);
}

/* Read-only counters for a focused test harness, not user data. */
unsigned long deck_touch_taps(void) { return taps; }
unsigned long deck_touch_swipes(void) { return swipes; }
