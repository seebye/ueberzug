#ifndef __UTIL_H__
#define __UTIL_H__

#define Py_INIT_ERROR -1
#define Py_INIT_SUCCESS 0
#define Py_ERROR NULL
#define Py_RETURN_ERROR return Py_ERROR
#define Py_INIT_RETURN_ERROR return Py_INIT_ERROR
#define Py_INIT_RETURN_SUCCESS return Py_INIT_SUCCESS

#define __raise(return_value, Exception, message...) { \
    char errorMessage[500]; \
    snprintf(errorMessage, 500, message); \
    PyErr_SetString( \
        PyExc_##Exception, \
        errorMessage); \
    return return_value; \
}
#define raise(Exception, message...) __raise(Py_ERROR, Exception, message)
#define raiseInit(Exception, message...) __raise(Py_INIT_ERROR, Exception, message)

#define ARRAY_LENGTH(stack_array) \
    (sizeof stack_array \
     ? sizeof stack_array / sizeof *stack_array \
     : 0)


#endif
