import abc
import enum
import distutils.util

import PIL.Image as Image

import ueberzug.batch as batch
import ueberzug.ui as ui
import ueberzug.xutil as xutil


class Executable:
    def __init__(self, windows, media):
        self.windows = windows
        self.media = media

    @abc.abstractmethod
    def execute(self, **kwargs):
        """Executes the action"""
        raise NotImplementedError()


class AddImageAction(Executable):
    """Displays the image according to the passed option.
    If there's already an image with the given identifier
    it's going to be replaced.
    """
    def execute(self, identifier, x, y, path, #pylint: disable=W0221,R0913
                width=None, height=None,
                max_width=None, max_height=None,
                draw=None):
        draw = (draw if isinstance(draw, bool)
                else distutils.util.strtobool(draw or 'True'))
        image = Image.open(path)
        x = int(x)
        y = int(y)
        width = int(width) if width else None
        height = int(height) if height else None
        max_width = int(max_width) if max_width else None
        max_height = int(max_height) if max_height else None
        image_rgb, mask = ui.get_image_and_mask(image)
        self.media[identifier] = ui.OverlayWindow.Placement(
            x, y, width, height, max_width, max_height,
            image_rgb, mask)

        if draw and self.windows:
            self.windows.draw()


class RemoveImageAction(Executable):
    """Removes the image with the passed identifier."""
    def execute(self, identifier, draw=None): #pylint: disable=W0221
        draw = (draw if isinstance(draw, bool)
                else distutils.util.strtobool(draw or 'True'))

        if identifier in self.media:
            del self.media[identifier]

            if draw and self.windows:
                self.windows.draw()


@enum.unique
class Command(str, enum.Enum):
    ADD = 'add', AddImageAction
    REMOVE = 'remove', RemoveImageAction

    def __new__(cls, identifier, action_class):
        inst = str.__new__(cls)
        inst._value_ = identifier
        inst.action_class = action_class
        return inst
