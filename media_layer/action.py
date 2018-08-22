import abc
import enum
import PIL.Image as Image

import media_layer.batch as batch
import media_layer.ui as ui
import media_layer.xutil as xutil


class Executable:
    def __init__(self, display, windows, media):
        self.display = display
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
                width=None, height=None, scale=None):
        image = Image.open(path)
        width = int(width) if width else image.width
        height = int(height) if height else image.height
        scale = float(scale) if scale else 1
        image = image.resize((int(width * scale),
                              int(height * scale)))
        image_rgb, mask = ui.get_image_and_mask(image)
        self.media[identifier] = ui.OverlayWindow.Placement(
            int(x), int(y), image_rgb, mask)
        self.windows.draw()


class RemoveImageAction(Executable):
    """Removes the image with the passed identifier."""
    def execute(self, identifier): #pylint: disable=W0221
        if identifier in self.media:
            del self.media[identifier]
            self.windows.draw()


class QueryWindowsAction(Executable):
    """Searches for added and removed tmux clients.
    Added clients: additional windows will be mapped
    Removed clients: existing windows will be destroyed
    """
    def execute(self): #pylint: disable=W0221
        parent_window_ids = set(xutil.get_parent_window_ids(self.display))
        map_current_windows = {window.parent_window.id: window
                               for window in self.windows}
        current_window_ids = map_current_windows.keys()
        diff_window_ids = parent_window_ids ^ current_window_ids
        added_window_ids = diff_window_ids & parent_window_ids
        removed_window_ids = diff_window_ids & current_window_ids

        if added_window_ids:
            added_windows = batch.BatchList([ui.OverlayWindow(self.display, wid, self.media)
                                             for wid in added_window_ids])
            added_windows.map()
            added_windows.draw()
            self.windows += added_windows

        for wid in removed_window_ids:
            window = map_current_windows.get(wid)
            if window:
                window.destroy()
                self.windows.remove(window)


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
