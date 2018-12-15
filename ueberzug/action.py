import abc
import enum
import attr

import PIL.Image as Image

import ueberzug.ui as ui
import ueberzug.conversion as conversion


@attr.s
class Action(metaclass=abc.ABCMeta):
    action = attr.ib(type=str, default=attr.Factory(
        lambda self: self.get_action_name(), takes_self=True))

    @staticmethod
    @abc.abstractmethod
    def get_action_name():
        """Returns the constant name which is associated to this action."""
        raise NotImplementedError()

    @abc.abstractmethod
    def apply(self, windows, view):
        """Executes the action on  the passed view and windows."""
        raise NotImplementedError()


@attr.s(kw_only=True)
class Drawable:
    """Defines the attributes of drawable actions."""
    draw = attr.ib(default=True, converter=conversion.to_bool)


@attr.s(kw_only=True)
class Identifiable:
    """Defines the attributes of actions
    which are associated to an identifier.
    """
    identifier = attr.ib(type=str)


@attr.s(kw_only=True)
class DrawAction(Action, Drawable, metaclass=abc.ABCMeta):
    """Defines actions which redraws all windows."""
    # pylint: disable=abstract-method

    def apply(self, windows, view):
        if self.draw and windows:
            windows.draw()


@attr.s(kw_only=True)
class ImageAction(DrawAction, Identifiable, metaclass=abc.ABCMeta):
    """Defines actions which are related to images."""
    # pylint: disable=abstract-method
    pass


@attr.s(kw_only=True)
class AddImageAction(ImageAction):
    """Displays the image according to the passed option.
    If there's already an image with the given identifier
    it's going to be replaced.
    """
    x = attr.ib(type=int, converter=int)
    y = attr.ib(type=int, converter=int)
    path = attr.ib(type=str)
    width = attr.ib(type=int, converter=int, default=0)
    max_width = attr.ib(type=int, converter=int, default=0)
    height = attr.ib(type=int, converter=int, default=0)
    max_height = attr.ib(type=int, converter=int, default=0)

    @staticmethod
    def get_action_name():
        return 'add'

    def apply(self, windows, view):
        image = Image.open(self.path)
        image_rgb, mask = ui.get_image_and_mask(image)
        view.media[self.identifier] = ui.OverlayWindow.Placement(
            self.x, self.y,
            self.width, self.height,
            self.max_width, self.max_height,
            image_rgb, mask)

        super().apply(windows, view)


@attr.s(kw_only=True)
class RemoveImageAction(ImageAction):
    """Removes the image with the passed identifier."""

    @staticmethod
    def get_action_name():
        return 'remove'

    def apply(self, windows, view):
        if self.identifier in view.media:
            del view.media[self.identifier]

            super().apply(windows, view)


@enum.unique
class Command(str, enum.Enum):
    ADD = AddImageAction
    REMOVE = RemoveImageAction

    def __new__(cls, action_class):
        inst = str.__new__(cls)
        inst._value_ = action_class.get_action_name()
        inst.action_class = action_class
        return inst
