// The desktop's slideshow view, applications/services/desktop/views/desktop_view_slideshow.c,
// against the stand-ins in tests/host/stubs_desktop and the ones below. The view loads its
// slideshow when it is entered and frees it when it exits, but the GUI draws on its own thread:
// view_dispatcher_set_current_view makes the view current before it calls the enter callback, so
// a draw can come first, and an exit frees the slideshow while the view is still current. On the
// device a draw before the first enter crashed with a NULL pointer dereference in
// slideshow_is_loaded, at boots after an update. Every draw must cope without a slideshow. When
// one is loaded and has one page, the update picture, the draw gives the reader its words as a
// focus note. Built with clang's address and undefined behaviour checks, so a read of a freed
// slideshow fails too.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../../Momentum-Firmware/applications/services/desktop/views/desktop_view_slideshow.c"

static int checks = 0;
static int failures = 0;

#define CHECK(cond)                                                \
    do {                                                           \
        checks++;                                                  \
        if(!(cond)) {                                              \
            failures++;                                            \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
        }                                                          \
    } while(0)

// The view: its callbacks and model, as view.c keeps them
struct View {
    ViewDrawCallback draw;
    ViewInputCallback input;
    ViewCallback enter;
    ViewCallback exit;
    void* context;
    void* model;
};

View* view_alloc(void) {
    return calloc(1, sizeof(View));
}

void view_free(View* view) {
    free(view->model);
    free(view);
}

void view_allocate_model(View* view, ViewModelType type, size_t size) {
    (void)type;
    view->model = calloc(1, size);
}

void view_set_context(View* view, void* context) {
    view->context = context;
}

void view_set_draw_callback(View* view, ViewDrawCallback callback) {
    view->draw = callback;
}

void view_set_input_callback(View* view, ViewInputCallback callback) {
    view->input = callback;
}

void view_set_enter_callback(View* view, ViewCallback callback) {
    view->enter = callback;
}

void view_set_exit_callback(View* view, ViewCallback callback) {
    view->exit = callback;
}

void* view_get_model(View* view) {
    return view->model;
}

void view_commit_model(View* view, bool update) {
    (void)view;
    (void)update;
}

// Timers that never fire
struct FuriTimer {
    int unused;
};

FuriTimer* furi_timer_alloc(FuriTimerCallback callback, FuriTimerType type, void* context) {
    (void)callback;
    (void)type;
    (void)context;
    return calloc(1, sizeof(FuriTimer));
}

void furi_timer_free(FuriTimer* timer) {
    free(timer);
}

void furi_timer_start(FuriTimer* timer, uint32_t ticks) {
    (void)timer;
    (void)ticks;
}

void furi_timer_stop(FuriTimer* timer) {
    (void)timer;
}

uint32_t furi_kernel_get_tick_frequency(void) {
    return 1000;
}

// The slideshow: slideshow_load gives the pages the test sets, or fails; the two questions are
// slideshow.c's own
static uint8_t load_pages = 1;
static bool load_ok = true;

Slideshow* slideshow_alloc(void) {
    return calloc(1, sizeof(Slideshow));
}

void slideshow_free(Slideshow* slideshow) {
    free(slideshow);
}

bool slideshow_load(Slideshow* slideshow, const char* fspath) {
    (void)fspath;
    slideshow->icon.frame_count = load_pages;
    slideshow->loaded = load_ok;
    return slideshow->loaded;
}

bool slideshow_is_loaded(Slideshow* slideshow) {
    return slideshow->loaded;
}

bool slideshow_is_one_page(Slideshow* slideshow) {
    return slideshow->loaded && (slideshow->icon.frame_count == 1);
}

void slideshow_goback(Slideshow* slideshow) {
    (void)slideshow;
}

bool slideshow_advance(Slideshow* slideshow) {
    (void)slideshow;
    return false;
}

static int pictures_drawn = 0;

void slideshow_draw(Slideshow* slideshow, Canvas* canvas, uint8_t x, uint8_t y) {
    (void)slideshow;
    (void)canvas;
    (void)x;
    (void)y;
    pictures_drawn++;
}

// The canvas: the last note and whether it was the focus
static char note[64];
static bool note_focus = false;

void canvas_clear(Canvas* canvas) {
    (void)canvas;
}

void canvas_tap_hint_note(Canvas* canvas, const char* text, bool focus) {
    (void)canvas;
    snprintf(note, sizeof(note), "%s", text);
    note_focus = focus;
}

static int completed = 0;

static void on_event(DesktopEvent event, void* context) {
    (void)context;
    if(event == DesktopSlideshowCompleted) completed++;
}

// One draw of the view, as the GUI thread does it, with what it gave the reader
static void draw(DesktopSlideshowView* instance) {
    note[0] = '\0';
    note_focus = false;
    pictures_drawn = 0;
    View* view = desktop_view_slideshow_get_view(instance);
    view->draw(NULL, view->model);
}

int main(void) {
    DesktopSlideshowView* instance = desktop_view_slideshow_alloc();
    desktop_view_slideshow_set_callback(instance, on_event, NULL);
    View* view = desktop_view_slideshow_get_view(instance);

    // A draw before the first enter: the view is current, its slideshow not yet loaded
    draw(instance);
    CHECK(pictures_drawn == 0);
    CHECK(note[0] == '\0');

    // The update picture, one page: drawn and spoken, as the focus, so the reader says it
    // without a key press on the home screen's layer
    load_pages = 1;
    load_ok = true;
    view->enter(view->context);
    draw(instance);
    CHECK(pictures_drawn == 1);
    CHECK(strcmp(note, "Firmware updated, press OK to continue") == 0);
    CHECK(note_focus);

    // A draw after the exit, which freed the slideshow, before the next view is current
    view->exit(view->context);
    draw(instance);
    CHECK(pictures_drawn == 0);
    CHECK(note[0] == '\0');

    // A slideshow of several pages is drawn but not given this note
    load_pages = 7;
    view->enter(view->context);
    draw(instance);
    CHECK(pictures_drawn == 1);
    CHECK(note[0] == '\0');
    view->exit(view->context);

    // A file that does not load ends the slideshow at once, and a draw before that is quiet
    load_pages = 1;
    load_ok = false;
    completed = 0;
    view->enter(view->context);
    CHECK(completed == 1);
    draw(instance);
    CHECK(pictures_drawn == 0);
    CHECK(note[0] == '\0');
    view->exit(view->context);

    desktop_view_slideshow_free(instance);
    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
