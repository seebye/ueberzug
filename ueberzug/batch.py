"""This module defines util classes
which allow to execute operations
for each element of a list of objects of the same class.
"""


class BatchList(list):
    """BatchList provides the execution of methods and field access
    for each element of a list of instances of the same class
    in a similar way to one of these instances it would.
    """

    class BatchMember:
        def __init__(self, outer, name):
            """
            Args:
                outer (BatchList): Outer class instance
            """
            self.outer = outer
            self.name = name

    class BatchField(BatchMember):
        def __get__(self, owner_instance, owner_class):
            return BatchList([instance.__getattribute__(self.name)
                              for instance in self.outer])

        def __set__(self, owner_instance, value):
            for instance in self.outer:
                instance.__setattr__(self.name, value)

        def __delete__(self, instance):
            for instance in self.outer:
                instance.__delattr__(self.name)

    class BatchMethod(BatchMember):
        def __call__(self, *args, **kwargs):
            return BatchList([instance.__getattribute__(self.name)(*args, **kwargs)
                              for instance in self.outer])

    def __new__(cls, *args, **kwargs):
        """As decorators only work if the class object contains the declarations,
        we need to create a subclass for each different type
        which is used in combination with BatchList.
        This is what this method is going to do.
        """
        if cls is not BatchList:
            return super().__new__(cls, *args, **kwargs)

        subclass = type(cls.__name__, (cls,), {})
        return subclass(*args, **kwargs)

    def __init__(self, collection: list):
        """
        Args:
            collection (List): List of target instances
        """
        if not collection:
            raise ValueError('BatchList needs to be initialised with an existing instance '
                             'as python declares (non static) class fields within __init__.')

        super().__init__(collection)
        self.__init_attributes__(self[0])
        self.__init_methods__(self[0])
        self.entered = False

    def __declare_decorator__(self, name, decorator):
        setattr(type(self), name, decorator)

    def __init_attributes__(self, target_instance):
        attributes = (vars(target_instance) \
                      if hasattr(target_instance, '__dict__')
                      else [])

        for name in filter(lambda name: not name.startswith('_'),
                           attributes):
            self.__declare_decorator__(name, BatchList.BatchField(self, name))

    def __init_methods__(self, target_instance):
        for name, value in filter(lambda i: not i[0].startswith('_'),
                                  vars(type(target_instance)).items()):
            if callable(value):
                self.__declare_decorator__(name, BatchList.BatchMethod(self, name))
            else:
                # should be an decorator
                self.__declare_decorator__(name, BatchList.BatchField(self, name))

    def __enter__(self):
        self.entered = True
        return BatchList([instance.__enter__() for instance in self])

    def __exit__(self, *args):
        for instance in self:
            instance.__exit__(*args)

    def append(self, item):
        if self.entered:
            item.__enter__()
        super().append(item)

    def extend(self, iterable):
        items = iterable

        if self.entered:
            items = []

            for i in iterable:
                items.append(i)
                i.__enter__()

        super().extend(items)

    def clear(self):
        if self.entered:
            for i in self:
                i.__exit__(None, None, None)
        super().clear()

    def insert(self, index, item):
        if self.entered:
            item.__enter__()
        super().insert(index, item)

    def copy(self):
        return BatchList(super().copy())

    def pop(self, *args):
        result = super().pop(*args)

        if self.entered:
            result.__exit__(None, None, None)

        return result

    def remove(self, value):
        if self.entered:
            value.__exit__(None, None, None)
        return super().remove(value)

    def __iadd__(self, other):
        if self.entered:
            for i in other:
                i.__enter__()
        super().__iadd__(other)

    def __isub__(self, other):
        for i in other:
            self.remove(i)

    def __add__(self, other):
        return BatchList(super().__add__(other))

    def __sub__(self, other):
        copied = self.copy()
        copied -= other
        return copied


if __name__ == '__main__':
    class FooBar:
        def __init__(self, a, b, c):
            self.mhm = a
            self.b = b
            self.c = c

        def ok(self):
            return self.b #'foo'

        @property
        def prop(self):
            return self.c #'supi'

    # print attributes
    #print(vars(FooBar()))
    # print properties and methods
    #print(vars(FooBar).keys())
    l = BatchList([FooBar('foo', 'bar', 'yay')])
    l += [FooBar('foobar', 'barfoo', 'yay foobar')]
    print('mhm', l.mhm)
    print('prop', l.prop)
    #print('ok', l.ok)
    print('ok call', l.ok())
