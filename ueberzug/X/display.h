#ifndef __DISPLAY_H__
#define __DISPLAY_H__

#include "python.h"

#include <X11/Xlib.h>


typedef struct {
    PyObject_HEAD
    // Always use the event_display
    // except for functions which return information
    // e.g. XGetGeometry.
    Display *event_display;
    Display *info_display;
    int bitmap_pad;
    int bitmap_unit;
    int screen;
    int screen_width;
    int screen_height;

    Atom wm_class;
    Atom wm_name;
    Atom wm_locale_name;
    Atom wm_normal_hints;
} DisplayObject;
extern PyTypeObject DisplayType;

#endif
