#include "python.h"

#include <X11/Xlib.h>
#include <X11/extensions/XRes.h>
#include <X11/extensions/XShm.h>

#include "util.h"
#include "display.h"


#define INVALID_PID (pid_t)-1


#define REOPEN_DISPLAY(display) \
    if (display != NULL) { \
        XCloseDisplay(display); \
    } \
    display = XOpenDisplay(NULL);

#define CLOSE_DISPLAY(display) \
    if (display != NULL) { \
        XCloseDisplay(display); \
        display = NULL; \
    }


static int
Display_init(DisplayObject *self, PyObject *args, PyObject *kwds) {
    // Two connections are opened as
    // a death lock can occur
    // if you listen for events
    // (this will happen in parallel in asyncio worker threads)
    // and request information (e.g. XGetGeometry)
    // simultaneously.
    REOPEN_DISPLAY(self->event_display);
    REOPEN_DISPLAY(self->info_display);

    if (self->event_display == NULL ||
            self->info_display == NULL) {
        raiseInit(OSError, "could not open a connection to the X server");
    }

    int _;
    if (!XResQueryExtension(self->info_display, &_, &_)) {
        raiseInit(OSError, "the extension XRes is required");
    }

    if (!XShmQueryExtension(self->event_display)) {
        raiseInit(OSError, "the extension Xext is required");
    }

    int screen = XDefaultScreen(self->info_display);
    self->screen_width = XDisplayWidth(self->info_display, screen);
    self->screen_height = XDisplayHeight(self->info_display, screen);
    self->bitmap_pad = XBitmapPad(self->info_display);
    self->bitmap_unit = XBitmapUnit(self->info_display);

    self->wm_class = XInternAtom(self->info_display, "WM_CLASS", False);
    self->wm_name = XInternAtom(self->info_display, "WM_NAME", False);
    self->wm_locale_name = XInternAtom(self->info_display, "WM_LOCALE_NAME", False);
    self->wm_normal_hints = XInternAtom(self->info_display, "WM_NORMAL_HINTS", False);

    Py_INIT_RETURN_SUCCESS;
}

static void
Display_dealloc(DisplayObject *self) {
    CLOSE_DISPLAY(self->event_display);
    CLOSE_DISPLAY(self->info_display);
    Py_TYPE(self)->tp_free((PyObject*)self);
}


static int
has_property(DisplayObject *self, Window window, Atom property) {
    Atom actual_type_return;
    int actual_format_return;
    unsigned long bytes_after_return;
    unsigned char* prop_to_return = NULL;
    unsigned long nitems_return;

    int status = XGetWindowProperty(
        self->info_display, window, property, 0,
        0L, False,
        AnyPropertyType,
        &actual_type_return,
        &actual_format_return,
        &nitems_return, &bytes_after_return, &prop_to_return);
    if (status == Success && prop_to_return) {
        XFree(prop_to_return);
    }
    return status == Success && !(actual_type_return == None && actual_format_return == 0);
}


static PyObject *
Display_get_child_window_ids(DisplayObject *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"parent_id", NULL};
    Window parent = XDefaultRootWindow(self->info_display);
    Window _, *children;
    unsigned int children_count;

    if (!PyArg_ParseTupleAndKeywords(
            args, kwds, "|k", kwlist,
            &parent)) {
        Py_RETURN_ERROR;
    }

    if (!XQueryTree(
            self->info_display, parent,
            &_, &_, &children, &children_count)) {
        raise(OSError, "failed to query child windows of %lu", parent);
    }

    PyObject *child_ids = PyList_New(0);
    if (children) {
        for (unsigned int i = 0; i < children_count; i++) {
            // assume that windows without essential properties
            // like the window title aren't shown to the user
            int is_helper_window = (
                !has_property(self, children[i], self->wm_class) &&
                !has_property(self, children[i], self->wm_name) &&
                !has_property(self, children[i], self->wm_locale_name) &&
                !has_property(self, children[i], self->wm_normal_hints));
            if (is_helper_window) {
                continue;
            }
            PyObject *py_window_id = Py_BuildValue("k", children[i]);
            PyList_Append(child_ids, py_window_id);
            Py_XDECREF(py_window_id);
        }
        XFree(children);
    }

    return child_ids;
}

static PyObject *
Display_get_window_pid(DisplayObject *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"window_id", NULL};
    Window window;
    long num_ids;
    int num_specs = 1;
    XResClientIdValue *client_ids;
    XResClientIdSpec client_specs[1];
    pid_t window_creator_pid = INVALID_PID;

    if (!PyArg_ParseTupleAndKeywords(
            args, kwds, "k", kwlist,
            &window)) {
        Py_RETURN_ERROR;
    }

    client_specs[0].client = window;
    client_specs[0].mask = XRES_CLIENT_ID_PID_MASK;
    if (Success != XResQueryClientIds(
            self->info_display, num_specs, client_specs,
            &num_ids, &client_ids)) {
        Py_RETURN_NONE;
    }

    for(int i = 0; i < num_ids; i++) {
        XResClientIdValue *value = client_ids + i;
        XResClientIdType type = XResGetClientIdType(value);

        if (type == XRES_CLIENT_ID_PID) {
            window_creator_pid = XResGetClientPid(value);
        }
    }

    XFree(client_ids);

    if (window_creator_pid != INVALID_PID) {
        return Py_BuildValue("i", window_creator_pid);
    }

    Py_RETURN_NONE;
}

static PyObject *
Display_wait_for_event(DisplayObject *self) {
    Py_BEGIN_ALLOW_THREADS
    XEvent event;
    XPeekEvent(self->event_display, &event);
    Py_END_ALLOW_THREADS
    Py_RETURN_NONE;
}

static PyObject *
Display_discard_event(DisplayObject *self) {
    Py_BEGIN_ALLOW_THREADS
    XEvent event;
    XNextEvent(self->event_display, &event);
    Py_END_ALLOW_THREADS
    Py_RETURN_NONE;
}

static PyObject *
Display_get_bitmap_format_scanline_pad(DisplayObject *self, void *closure) {
    return Py_BuildValue("i", self->bitmap_pad);
}

static PyObject *
Display_get_bitmap_format_scanline_unit(DisplayObject *self, void *closure) {
    return Py_BuildValue("i", self->bitmap_unit);
}

static PyObject *
Display_get_screen_width(DisplayObject *self, void *closure) {
    return Py_BuildValue("i", self->screen_width);
}

static PyObject *
Display_get_screen_height(DisplayObject *self, void *closure) {
    return Py_BuildValue("i", self->screen_height);
}


static PyGetSetDef Display_properties[] = {
    {"bitmap_format_scanline_pad", (getter)Display_get_bitmap_format_scanline_pad,
     .doc = "int: Each scanline must be padded to a multiple of bits of this value."},
    {"bitmap_format_scanline_unit", (getter)Display_get_bitmap_format_scanline_unit,
     .doc = "int:\n"
            "    The size of a bitmap's scanline unit in bits.\n"
            "    The scanline is calculated in multiples of this value."},
    {"screen_width", (getter)Display_get_screen_width,
     .doc = "int: The width of the default screen at the time the connection to X11 was opened."},
    {"screen_height", (getter)Display_get_screen_width,
     .doc = "int: The height of the default screen at the time the connection to X11 was opened."},
    {NULL}  /* Sentinel */
};


static PyMethodDef Display_methods[] = {
    {"wait_for_event", (PyCFunction)Display_wait_for_event,
     METH_NOARGS,
     "Waits for an event to occur. till an event occur."},
    {"discard_event", (PyCFunction)Display_discard_event,
     METH_NOARGS,
     "Discards the first event from the event queue."},
    {"get_child_window_ids", (PyCFunction)Display_get_child_window_ids,
     METH_VARARGS | METH_KEYWORDS,
     "Queries for the ids of the children of the window with the passed identifier.\n"
     "\n"
     "Args:\n"
     "    parent_id (int): optional\n"
     "        the id of the window for which to query for the ids of its children\n"
     "        if it's not specified the id of the default root window will be used\n"
     "\n"
     "Returns:\n"
     "    list of ints: the ids of the child windows"},
    {"get_window_pid", (PyCFunction)Display_get_window_pid,
     METH_VARARGS | METH_KEYWORDS,
     "Tries to figure out the pid of the process which created the window with the passed id.\n"
     "\n"
     "Args:\n"
     "    window_id (int): the window id for which to retrieve information\n"
     "\n"
     "Returns:\n"
     "    int or None: the pid of the creator of the window"},
    {NULL}  /* Sentinel */
};

PyTypeObject DisplayType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "ueberzug.X.Display",
    .tp_doc = "X11 display\n",
    .tp_basicsize = sizeof(DisplayObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .tp_new = PyType_GenericNew,
    .tp_init = (initproc)Display_init,
    .tp_dealloc = (destructor)Display_dealloc,
    .tp_getset = Display_properties,
    .tp_methods = Display_methods,
};
