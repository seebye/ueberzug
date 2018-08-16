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
        # magic methods should be handled by categories, e.g. comporators by one method etc.
        # but.. it's not really needed in this project so.. let's be lazy..
        return BatchList([instance.__enter__() for instance in self])

    def __exit__(self, *args):
        for instance in self:
            instance.__exit__(*args)


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
