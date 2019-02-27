import abc
import enum
import asyncio
import os.path

import PIL.Image as Image
import attr

import ueberzug.geometry as geometry
import ueberzug.scaling as scaling
import ueberzug.ui as ui
import ueberzug.conversion as conversion


@attr.s
class Action(metaclass=abc.ABCMeta):
    """Describes the structure used to define actions classes.

    Defines a general interface used to implement the building of commands
    and their execution.
    """
    action = attr.ib(type=str, default=attr.Factory(
        lambda self: self.get_action_name(), takes_self=True))

    @staticmethod
    @abc.abstractmethod
    def get_action_name():
        """Returns the constant name which is associated to this action."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def apply(self, parser_object, windows, view):
        """Executes the action on  the passed view and windows."""
        raise NotImplementedError()


@attr.s(kw_only=True)
class Drawable:
    """Defines the attributes of drawable actions."""
    draw = attr.ib(default=True, converter=conversion.to_bool)
    synchronously_draw = attr.ib(default=False, converter=conversion.to_bool)


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
    __redraw_scheduled = False

    @staticmethod
    def schedule_redraw(windows):
        """Creates a async function which redraws every window
        if there is no unexecuted function
        (returned by this function)
        which does the same.

        Args:
            windows (batch.BatchList of ui.OverlayWindow):
                the windows to be redrawn

        Returns:
            function: the redraw function or None
        """
        if not DrawAction.__redraw_scheduled:
            DrawAction.__redraw_scheduled = True

            async def redraw():
                windows.draw()
                DrawAction.__redraw_scheduled = False
            return redraw()
        return None

    async def apply(self, parser_object, windows, view):
        if self.draw:
            if self.synchronously_draw:
                windows.draw()
                # force coroutine switch
                await asyncio.sleep(0)
                return

            function = self.schedule_redraw(windows)
            if function:
                asyncio.ensure_future(function)


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
    INDEX_ALPHA_CHANNEL = 3

    x = attr.ib(type=int, converter=int)
    y = attr.ib(type=int, converter=int)
    path = attr.ib(type=str)
    width = attr.ib(type=int, converter=int, default=0)
    height = attr.ib(type=int, converter=int, default=0)
    scaling_position_x = attr.ib(type=float, converter=float, default=0)
    scaling_position_y = attr.ib(type=float, converter=float, default=0)
    scaler = attr.ib(
        type=str, default=scaling.ContainImageScaler.get_scaler_name())
    # deprecated
    max_width = attr.ib(type=int, converter=int, default=0)
    max_height = attr.ib(type=int, converter=int, default=0)

    @staticmethod
    def get_action_name():
        return 'add'

    @staticmethod
    def load_image(path: str) -> Image:
        """Loads the image and removes the opacity mask.

        Args:
            path (str): the path of the image file

        Returns:
            Image: rgb image
        """
        image = Image.open(path)

        if image.mode == 'P':
            image = image.convert('RGBA')

        if image.mode in 'RGBA' and len(image.getbands()) == 4:
            image.load()
            image_alpha = image.split()[AddImageAction.INDEX_ALPHA_CHANNEL]
            image_rgb = Image.new("RGB", image.size, color=(255, 255, 255))
            image_rgb.paste(image, mask=image_alpha)
            image = image_rgb
        else:
            # convert to supported image formats
            image.load()
            image_rgb = Image.new("RGB", image.size, color=(255, 255, 255))
            image_rgb.paste(image)
            image = image_rgb

        return image

    async def apply(self, parser_object, windows, view):
        try:
            old_placement = view.media.get(self.identifier)
            cache = old_placement and old_placement.cache
            image = old_placement and old_placement.image
            last_modified = old_placement and old_placement.last_modified
            current_last_modified = os.path.getmtime(self.path)

            if (not image
                    or last_modified < current_last_modified
                    or self.path != old_placement.path):
                last_modified = current_last_modified
                image = self.load_image(self.path)
                cache = None

            view.media[self.identifier] = ui.OverlayWindow.Placement(
                self.x, self.y,
                self.max_width or self.width, self.max_height or self.height,
                geometry.Point(self.scaling_position_x,
                               self.scaling_position_y),
                scaling.ScalerOption(self.scaler).scaler_class(),
                self.path, image, last_modified, cache)
        finally:
            await super().apply(parser_object, windows, view)


@attr.s(kw_only=True)
class RemoveImageAction(ImageAction):
    """Removes the image with the passed identifier."""

    @staticmethod
    def get_action_name():
        return 'remove'

    async def apply(self, parser_object, windows, view):
        try:
            if self.identifier in view.media:
                del view.media[self.identifier]
        finally:
            await super().apply(parser_object, windows, view)


@enum.unique
class Command(str, enum.Enum):
    ADD = AddImageAction
    REMOVE = RemoveImageAction

    def __new__(cls, action_class):
        inst = str.__new__(cls)
        inst._value_ = action_class.get_action_name()
        inst.action_class = action_class
        return inst
