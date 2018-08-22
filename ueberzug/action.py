import abc
import enum
import distutils.util

import PIL.Image as Image

import ueberzug.batch as batch
import ueberzug.ui as ui
import ueberzug.xutil as xutil


class Executable:
    def __init__(self, display, window_factory, windows, media):
        self.display = display
        self.window_factory = window_factory
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
        draw = draw or 'True'
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

        if distutils.util.strtobool(draw):
            self.windows.draw()


class RemoveImageAction(Executable):
    """Removes the image with the passed identifier."""
    def execute(self, identifier, draw=None): #pylint: disable=W0221
        draw = draw or 'True'

        if identifier in self.media:
            del self.media[identifier]

            if distutils.util.strtobool(draw):
                self.windows.draw()


class QueryWindowsAction(Executable):
    """Searches for added and removed tmux clients.
    Added clients: additional windows will be mapped
    Removed clients: existing windows will be destroyed
    """
    def execute(self): #pylint: disable=W0221
        parent_window_infos = xutil.get_parent_window_infos(self.display)
        map_parent_window_id_info = {info.window_id: info
                                     for info in parent_window_infos}
        parent_window_ids = map_parent_window_id_info.keys()
        map_current_windows = {window.parent_window.id: window
                               for window in self.windows}
        current_window_ids = map_current_windows.keys()
        diff_window_ids = parent_window_ids ^ current_window_ids
        added_window_ids = diff_window_ids & parent_window_ids
        removed_window_ids = diff_window_ids & current_window_ids

        if added_window_ids:
            self.windows += self.window_factory.create(*[
                map_parent_window_id_info.get(wid)
                for wid in added_window_ids
            ])

        if removed_window_ids:
            self.windows -= [
                map_current_windows.get(wid)
                for wid in removed_window_ids
            ]


@enum.unique
class Command(str, enum.Enum):
    ADD = 'add', AddImageAction
    REMOVE = 'remove', RemoveImageAction
    FOCUS_CHANGED = 'query_windows', QueryWindowsAction

    def __new__(cls, identifier, action_class):
        inst = str.__new__(cls)
        inst._value_ = identifier
        inst.action_class = action_class
        return inst
