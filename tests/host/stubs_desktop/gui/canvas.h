// The parts of gui/canvas.h that the desktop's slideshow view uses, for its host test.
#pragma once
#include <stdbool.h>

typedef struct Canvas Canvas;

void canvas_clear(Canvas* canvas);
void canvas_tap_hint_note(Canvas* canvas, const char* text, bool focus);
