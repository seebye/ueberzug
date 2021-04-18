#include "python.h"
#include "display.h"
#include "window.h"
#include "Xshm.h"


static PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    .m_name = "ueberzug.X",
    .m_doc = "Modul which implements the interaction with the Xshm extension.",
    .m_size = -1,
};


PyMODINIT_FUNC
PyInit_X(void) {
    PyObject *module_instance;
    if (PyType_Ready(&DisplayType) < 0 ||
            PyType_Ready(&WindowType) < 0 ||
            PyType_Ready(&ImageType) < 0) {
        return NULL;
    }

    module_instance = PyModule_Create(&module);
    if (module_instance == NULL) {
        return NULL;
    }

    Py_INCREF(&DisplayType);
    Py_INCREF(&WindowType);
    Py_INCREF(&ImageType);
    PyModule_AddObject(module_instance, "Display", (PyObject*)&DisplayType);
    PyModule_AddObject(module_instance, "OverlayWindow", (PyObject*)&WindowType);
    PyModule_AddObject(module_instance, "Image", (PyObject*)&ImageType);
    return module_instance;
}
