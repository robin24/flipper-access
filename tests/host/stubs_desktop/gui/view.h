// The parts of gui/view.h and the input types that the desktop's slideshow view uses, for its
// host test, tests/host/test_desktop_slideshow.c, which also defines the functions.
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <gui/canvas.h>

typedef enum {
    InputKeyUp,
    InputKeyDown,
    InputKeyRight,
    InputKeyLeft,
    InputKeyOk,
    InputKeyBack,
} InputKey;

typedef enum {
    InputTypePress,
    InputTypeRelease,
    InputTypeShort,
    InputTypeLong,
    InputTypeRepeat,
} InputType;

typedef struct {
    InputKey key;
    InputType type;
} InputEvent;

typedef enum {
    ViewModelTypeNone,
    ViewModelTypeLockFree,
    ViewModelTypeLocking,
} ViewModelType;

typedef struct View View;
typedef void (*ViewDrawCallback)(Canvas* canvas, void* model);
typedef bool (*ViewInputCallback)(InputEvent* event, void* context);
typedef void (*ViewCallback)(void* context);

View* view_alloc(void);
void view_free(View* view);
void view_allocate_model(View* view, ViewModelType type, size_t size);
void view_set_context(View* view, void* context);
void view_set_draw_callback(View* view, ViewDrawCallback callback);
void view_set_input_callback(View* view, ViewInputCallback callback);
void view_set_enter_callback(View* view, ViewCallback callback);
void view_set_exit_callback(View* view, ViewCallback callback);
void* view_get_model(View* view);
void view_commit_model(View* view, bool update);
