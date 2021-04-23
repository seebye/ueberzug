#ifndef __PYTHON_H__
#define __PYTHON_H__

#ifndef __linux__
#error OS unsupported
#endif

#define PY_SSIZE_T_CLEAN  // Make "s#" use Py_ssize_t rather than int.
#include <Python.h>

#endif
