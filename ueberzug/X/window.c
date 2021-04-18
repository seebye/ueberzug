#include "python.h"

#include <stdbool.h>
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/extensions/shape.h>

#include "util.h"
#include "display.h"


typedef struct {
    PyObject_HEAD
    DisplayObject *display_pyobject;
    Window parent;
    Window window;
    unsigned int width;
    unsigned int height;
} WindowObject;


static inline Display *
get_event_display(WindowObject *self) {
    return self->display_pyobject->event_display;
}

static inline Display *
get_info_display(WindowObject *self) {
    return self->display_pyobject->info_display;
}

static void
Window_create(WindowObject *self) {
    Window _0; int _1; unsigned int _2;
    XGetGeometry(
        get_info_display(self),
        self->parent,
        &_0, &_1, &_1,
        &self->width, &self->height,
        &_2, &_2);

    Display *display = get_event_display(self);
    int screen = XDefaultScreen(display);
    Visual *visual = XDefaultVisual(display, screen);
    unsigned long attributes_mask =
        CWEventMask | CWBackPixel | CWColormap | CWBorderPixel;
    XSetWindowAttributes attributes;
    attributes.event_mask = ExposureMask;
    attributes.colormap = XCreateColormap(
        display, XDefaultRootWindow(display),
        visual, AllocNone);
    attributes.background_pixel = 0;
    attributes.border_pixel = 0;

    self->window = XCreateWindow(
        display, self->parent,
        0, 0, self->width, self->height, 0,
        DefaultDepth(display, screen),
        InputOutput, visual,
        attributes_mask, &attributes);
}

static void
set_subscribed_events(Display *display, Window window, long event_mask) {
    XSetWindowAttributes attributes;
    attributes.event_mask = event_mask;
    XChangeWindowAttributes(
        display, window,
        CWEventMask , &attributes);
}

static void
Window_finalise(WindowObject *self) {
    if (self->window) {
        Display *display = get_event_display(self);
        set_subscribed_events(
            display, self->parent, NoEventMask);
        XDestroyWindow(display, self->window);
        XFlush(display);
    }

    Py_CLEAR(self->display_pyobject);
    self->window = 0;
}

static inline void
set_xshape_mask(Display *display, Window window, int kind, XRectangle area[], int area_length) {
    XShapeCombineRectangles(
        display, window,
        kind,
        0, 0, area, area_length,
        ShapeSet, 0);
}

static inline void
set_input_mask(Display *display, Window window, XRectangle area[], int area_length) {
    set_xshape_mask(
        display, window, ShapeInput, area, area_length);
}

static inline void
set_visibility_mask(Display *display, Window window, XRectangle area[], int area_length) {
    set_xshape_mask(
        display, window, ShapeBounding, area, area_length);
}

static int
Window_init(WindowObject *self, PyObject *args, PyObject *kwds) {
    static XRectangle empty_area[0] = {};
    static char *kwlist[] = {"display", "parent", NULL};
    PyObject *display_pyobject;
    Window parent;

    if (!PyArg_ParseTupleAndKeywords(
            args, kwds, "O!k", kwlist,
            &DisplayType, &display_pyobject, &parent)) {
        Py_INIT_RETURN_ERROR;
    }

    if (self->display_pyobject) {
        Window_finalise(self);
    }

    Py_INCREF(display_pyobject);
    self->display_pyobject = (DisplayObject*)display_pyobject;
    Display *display = get_event_display(self);
    self->parent = parent;
    Window_create(self);
    set_subscribed_events(
        display, self->parent, StructureNotifyMask);
    set_input_mask(
        display, self->window,
        empty_area, ARRAY_LENGTH(empty_area));
    set_visibility_mask(
        display, self->window,
        empty_area, ARRAY_LENGTH(empty_area));
    XMapWindow(display, self->window);

    Py_INIT_RETURN_SUCCESS;
}

static void
Window_dealloc(WindowObject *self) {
    Window_finalise(self);
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject *
Window_set_visibility_mask(WindowObject *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"area", NULL};
    PyObject *py_area;
    Py_ssize_t area_length;

    if (!PyArg_ParseTupleAndKeywords(
            args, kwds, "O!", kwlist,
            &PyList_Type, &py_area)) {
        Py_RETURN_ERROR;
    }

    area_length = PyList_Size(py_area);
    XRectangle area[area_length];

    for (Py_ssize_t i = 0; i < area_length; i++) {
        short x, y;
        unsigned short width, height; 
        PyObject *py_rectangle = PyList_GetItem(py_area, i);

        if (!PyObject_TypeCheck(py_rectangle, &PyTuple_Type)) {
            raise(ValueError, "Expected a list of a tuple of ints!");
        }
        if (!PyArg_ParseTuple(
                py_rectangle, "hhHH",
                &x, &y, &width, &height)) {
            raise(ValueError,
                  "Expected a rectangle to be a "
                  "tuple of (x: int, y: int, width: int, height: int)!");
        }

        area[i].x = x;
        area[i].y = y;
        area[i].width = width;
        area[i].height = height;
    }
    
    set_visibility_mask(
        get_event_display(self),
        self->window,
        area, area_length);

    Py_RETURN_NONE;
}

static PyObject *
Window_draw(WindowObject *self) {
    XFlush(get_event_display(self));
    Py_RETURN_NONE;
}

static PyObject *
Window_get_id(WindowObject *self, void *closure) {
    return Py_BuildValue("k", self->window);
}

static PyObject *
Window_get_parent_id(WindowObject *self, void *closure) {
    return Py_BuildValue("k", self->parent);
}

static PyObject *
Window_get_width(WindowObject *self, void *closure) {
    return Py_BuildValue("I", self->width);
}

static PyObject *
Window_get_height(WindowObject *self, void *closure) {
    return Py_BuildValue("I", self->height);
}

static PyObject *
Window_process_event(WindowObject *self) {
    XEvent event;
    XAnyEvent *metadata = &event.xany;
    Display *display = get_event_display(self);

    if (!XPending(display)) {
        Py_RETURN_FALSE;
    }

    XPeekEvent(display, &event);

    if (! (event.type == Expose && metadata->window == self->window) &&
             ! (event.type == ConfigureNotify && metadata->window == self->parent)) {
        Py_RETURN_FALSE;
    }

    XNextEvent(display, &event);

    switch (event.type) {
        case Expose:
            if(event.xexpose.count == 0) {
                Py_XDECREF(PyObject_CallMethod(
                    (PyObject*)self, "draw", NULL));
            }
            break;
        case ConfigureNotify: {
                unsigned int delta_width = 
                    ((unsigned int)event.xconfigure.width) - self->width;
                unsigned int delta_height = 
                    ((unsigned int)event.xconfigure.height) - self->height;
                
                if (delta_width != 0 || delta_height != 0) {
                    self->width = (unsigned int)event.xconfigure.width;
                    self->height = (unsigned int)event.xconfigure.height;
                    XResizeWindow(display, self->window, self->width, self->height);
                }
                
                if (delta_width > 0 || delta_height > 0) {
                    Py_XDECREF(PyObject_CallMethod(
                        (PyObject*)self, "draw", NULL));
                }
                else {
                    XFlush(display);
                }
            }
            break;
    }

    Py_RETURN_TRUE;
}

static PyGetSetDef Window_properties[] = {
    {"id", (getter)Window_get_id, .doc = "int: the X11 id of this window."},
    {"parent_id", (getter)Window_get_parent_id, .doc = "int: the X11 id of the parent window."},
    {"width", (getter)Window_get_width, .doc = "int: the width of this window."},
    {"height", (getter)Window_get_height, .doc = "int: the height of this window."},
    {NULL}  /* Sentinel */
};

static PyMethodDef Window_methods[] = {
    {"draw", (PyCFunction)Window_draw,
     METH_NOARGS,
     "Redraws the window."},
    {"set_visibility_mask", (PyCFunction)Window_set_visibility_mask,
     METH_VARARGS | METH_KEYWORDS,
     "Specifies the part of the window which should be visible.\n"
     "\n"
     "Args:\n"
     "    area (tuple of (tuple of (x: int, y: int, width: int, height: int))):\n"
     "        the visible area specified by rectangles"},
    {"process_event", (PyCFunction)Window_process_event,
     METH_NOARGS,
     "Processes the next X11 event if it targets this window.\n"
     "\n"
     "Returns:\n"
     "    bool: True if an event was processed"},
    {NULL}  /* Sentinel */
};

PyTypeObject WindowType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "ueberzug.X.OverlayWindow",
    .tp_doc = 
        "Basic implementation of an overlay window\n"
        "\n"
        "Args:\n"
        "    display (ueberzug.X.Display): the X11 display\n"
        "    parent (int): the parent window of this window",
    .tp_basicsize = sizeof(WindowObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .tp_new = PyType_GenericNew,
    .tp_init = (initproc)Window_init,
    .tp_dealloc = (destructor)Window_dealloc,
    .tp_getset = Window_properties,
    .tp_methods = Window_methods,
};
