import abc
import enum
import attr

import PIL.Image as Image

import ueberzug.ui as ui
import ueberzug.conversion as conversion


@attr.s
class Action(metaclass=abc.ABCMeta):
    action = attr.ib(type=str)

    @abc.abstractmethod
    def apply(self, windows, view):
        """Executes the action on  the passed view and windows."""
        raise NotImplementedError()


@attr.s
class DrawAction(Action, metaclass=abc.ABCMeta):
    # pylint: disable=abstract-method
    draw = attr.ib(default=True, converter=conversion.to_bool)


@attr.s
class ImageAction(DrawAction, metaclass=abc.ABCMeta):
    # pylint: disable=abstract-method
    identifier = attr.ib(default=True)


@attr.s(kw_only=True)
class AddImageAction(ImageAction):
    """Displays the image according to the passed option.
    If there's already an image with the given identifier
    it's going to be replaced.
    """
    x = attr.ib(converter=int)
    y = attr.ib(converter=int)
    path = attr.ib(type=str)
    width = attr.ib(converter=int, default=0)
    max_width = attr.ib(converter=int, default=0)
    height = attr.ib(converter=int, default=0)
    max_height = attr.ib(converter=int, default=0)

    def apply(self, windows, view):
        image = Image.open(self.path)
        image_rgb, mask = ui.get_image_and_mask(image)
        view.media[self.identifier] = ui.OverlayWindow.Placement(
            self.x, self.y,
            self.width, self.height,
            self.max_width, self.max_height,
            image_rgb, mask)

        if self.draw and windows:
            windows.draw()


@attr.s(kw_only=True)
class RemoveImageAction(ImageAction):
    """Removes the image with the passed identifier."""
    def apply(self, windows, view):
        if self.identifier in view.media:
            del view.media[self.identifier]

            if self.draw and windows:
                windows.draw()


@enum.unique
class Command(str, enum.Enum):
    ADD = 'add', AddImageAction
    REMOVE = 'remove', RemoveImageAction

    def __new__(cls, identifier, action_class):
        inst = str.__new__(cls)
        inst._value_ = identifier
        inst.action_class = action_class
        return inst
