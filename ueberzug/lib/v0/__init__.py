import abc
import enum
import subprocess
import threading
import json
import collections
import contextlib

import attr

import ueberzug.action as _action


class Visibility(enum.Enum):
    """Enum which defines the different visibility states."""
    VISIBLE = enum.auto()
    INVISIBLE = enum.auto()


class Placement:
    __initialised = False
    __DEFAULT_VALUES = {str: '', int: 0}
    __ATTRIBUTES = {attribute.name: attribute
                    for attribute in attr.fields(_action.AddImageAction)}
    __EMPTY_BASE_PAIRS = (
        lambda attributes, default_values:
        {attribute.name: default_values[attribute.type]
         for attribute in attributes.values()
         if (attribute.default == attr.NOTHING
             and attribute.init)}
        )(__ATTRIBUTES, __DEFAULT_VALUES)

    def __init__(self, canvas, identifier,
                 visibility: Visibility = Visibility.INVISIBLE,
                 **kwargs):
        self.__canvas = canvas
        self.__identifier = identifier
        self.__visibility = False
        self.__data = {}
        self.__initialised = True
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.visibility = visibility

    @property
    def canvas(self):
        return self.__canvas

    @property
    def identifier(self):
        return self.__identifier

    @property
    def visibility(self):
        return self.__visibility

    @visibility.setter
    def visibility(self, value):
        if self.__visibility != value:
            if value is Visibility.INVISIBLE:
                self.__remove()
            elif value is Visibility.VISIBLE:
                self.__update()
            else:
                raise TypeError("expected an instance of Visibility")
            self.__visibility = value

    def __remove(self):
        self.__canvas.enqueue(
            _action.RemoveImageAction(identifier=self.identifier))
        self.__canvas.request_transmission()

    def __update(self):
        self.__canvas.enqueue(_action.AddImageAction(**{
            **self.__data,
            **attr.asdict(_action.Identifiable(identifier=self.identifier))
        }))
        self.__canvas.request_transmission()

    def __getattr__(self, name):
        if name not in self.__ATTRIBUTES:
            raise AttributeError("There is no attribute named %s" % name)

        attribute = self.__ATTRIBUTES[name]

        if name in self.__data:
            return self.__data[name]
        if attribute.default != attr.NOTHING:
            return attribute.default
        return None

    def __setattr__(self, name, value):
        if not self.__initialised:
            super().__setattr__(name, value)
            return
        if name not in self.__ATTRIBUTES:
            if hasattr(self, name):
                super().__setattr__(name, value)
                return
            raise AttributeError("There is no attribute named %s" % name)

        data = dict(self.__data)
        self.__data.update(attr.asdict(_action.AddImageAction(**{
            **self.__EMPTY_BASE_PAIRS,
            **self.__data,
            **attr.asdict(_action.Identifiable(identifier=self.identifier)),
            name: value
        })))

        # remove the key's of the empty base pairs
        # so the developer is forced to set them by himself
        for key in self.__EMPTY_BASE_PAIRS:
            if key not in data and key != name:
                del self.__data[key]

        if self.visibility is Visibility.VISIBLE:
            self.__update()


class UeberzugProcess:
    __KILL_TIMEOUT_SECONDS = 1
    __BUFFER_SIZE_BYTES = 50 * 1024

    def __init__(self, options):
        self.__start_options = options
        self.__process = None

    @property
    def stdin(self):
        return self.__process.stdin

    @property
    def running(self):
        return (self.__process is not None
                and self.__process.poll() is None)

    @property
    def responsive(self):
        return self.running and not self.__process.stdin.closed

    def start(self):
        if self.responsive:
            return
        if self.running:
            self.stop()

        self.__process = subprocess.Popen(
            ['ueberzug', 'layer'] + self.__start_options,
            stdin=subprocess.PIPE,
            bufsize=self.__BUFFER_SIZE_BYTES,
            universal_newlines=True)

    def stop(self):
        if self.running:
            timer_kill = threading.Timer(
                self.__KILL_TIMEOUT_SECONDS,
                self.__process.kill,
                [])

            try:
                self.__process.terminate()
                timer_kill.start()
                self.__process.communicate()
            finally:
                timer_kill.cancel()


class CommandTransmitter:
    """Describes the structure used to define command transmitter classes.

    Defines a general interface used to implement different ways
    of storing and transmitting commands to ueberzug processes.
    """

    def __init__(self, process):
        self._process = process

    @abc.abstractmethod
    def enqueue(self, action: _action.Action):
        """Enqueues a command.

        Args:
            action (action.Action): the command which should be executed
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def transmit(self):
        """Transmits every command in the queue."""
        raise NotImplementedError()


class DequeCommandTransmitter(CommandTransmitter):
    """Implements the command transmitter with a dequeue."""

    def __init__(self, process):
        super().__init__(process)
        self.__queue_commands = collections.deque()

    def enqueue(self, action: _action.Action):
        self.__queue_commands.append(action)

    def transmit(self):
        while self.__queue_commands:
            command = self.__queue_commands.popleft()
            self._process.stdin.write(json.dumps({
                **attr.asdict(command),
                **attr.asdict(_action.Drawable(draw=not self.__queue_commands))
            }))
            self._process.stdin.write('\n')
        self._process.stdin.flush()


class LazyCommandTransmitter(CommandTransmitter):
    """Implements lazily transmitting commands as decorator class.

    Ignores calls of the transmit method.
    """
    def __init__(self, transmitter):
        super().__init__(None)
        self.transmitter = transmitter

    def enqueue(self, action: _action.Action):
        self.transmitter.enqueue(action)

    def transmit(self):
        pass

    def force_transmit(self):
        """Executes the transmit method of the decorated CommandTransmitter."""
        self.transmitter.transmit()


class Canvas:
    def __init__(self, debug=False):
        self.__process = UeberzugProcess([] if debug else ['--silent'])
        self.__transmitter = DequeCommandTransmitter(self.__process)
        self.__used_identifiers = set()

    def create_placement(self, identifier, *args, **kwargs):
        if identifier in self.__used_identifiers:
            raise ValueError("Identifier '%s' is already taken." % identifier)
        self.__used_identifiers.add(identifier)
        return Placement(self, identifier, *args, **kwargs)

    @property
    @contextlib.contextmanager
    def lazy_drawing(self):
        try:
            self.__transmitter.transmit()
            self.__transmitter = LazyCommandTransmitter(self.__transmitter)
            yield
            self.__transmitter.force_transmit()
        finally:
            self.__transmitter = self.__transmitter.transmitter

    def __call__(self, function):
        def decorator(*args, **kwargs):
            with self:
                return function(*args, canvas=self, **kwargs)
        return decorator

    def __enter__(self):
        self.__process.start()
        return self

    def __exit__(self, *args):
        self.__process.stop()

    def enqueue(self, command: _action.Action):
        if not self.__process.responsive:
            self.__process.start()

        self.__transmitter.enqueue(command)

    def request_transmission(self):
        if not self.__process.responsive:
            return

        self.__transmitter.transmit()
