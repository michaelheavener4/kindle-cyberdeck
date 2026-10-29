/* mGBA's SDL2 fallback still asks for an OpenGL window and an accelerated
 * renderer. Xephyr's 8-bit Kindle display has neither. Preload only into
 * mGBA: keep its emulation, saves and input handling, but use SDL software.
 * No SDL headers are needed; these are the public SDL2 function signatures.
 */
extern void *dlsym(void *, const char *);
extern long write(int, const void *, unsigned long);

static void report_error(void) {
    typedef const char *(*error_fn)(void);
    error_fn error = (error_fn)dlsym((void *)-1, "SDL_GetError");
    const char *text = error();
    unsigned long len = 0;
    while (text[len]) ++len;
    write(2, "Kindle SDL: ", 12);
    write(2, text, len);
    write(2, "\n", 1);
}

void *SDL_CreateWindow(const char *title, int x, int y, int w, int h,
                       unsigned int flags) {
    typedef void *(*create_fn)(const char *, int, int, int, int, unsigned int);
    create_fn create = (create_fn)dlsym((void *)-1, "SDL_CreateWindow");
    void *window = create(title, x, y, w, h, flags & ~2u);
    if (!window) report_error();
    return window; /* SDL_WINDOW_OPENGL cleared */
}

void *SDL_GL_CreateContext(void *window) {
    (void)window;
    return (void *)0; /* Select mGBA's software backend. */
}

void *SDL_CreateRenderer(void *window, int index, unsigned int flags) {
    typedef void *(*create_fn)(void *, int, unsigned int);
    create_fn create = (create_fn)dlsym((void *)-1, "SDL_CreateRenderer");
    (void)flags;
    void *renderer = create(window, index, 1u);
    if (!renderer) report_error();
    return renderer; /* SDL_RENDERER_SOFTWARE */
}
