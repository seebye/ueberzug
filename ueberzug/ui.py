"""This module contains user interface related classes and methods.
"""
import abc
import weakref
import attr

import Xlib.X as X
import Xlib.display as Xdisplay
import Xlib.ext.shape as Xshape
import Xlib.protocol.event as Xevent
import PIL.Image as Image

import ueberzug.xutil as xutil
import ueberzug.geometry as geometry
import ueberzug.scaling as scaling
import Xshm


def roundup(value, unit):
    return ((value + (unit - 1)) & ~(unit - 1)) >> 3


def get_visual_id(screen, depth: int):
    """Determines the visual id
    for the given screen and - depth.
    """
    try:
        return next(filter(lambda i: i.depth == depth,
                           screen.allowed_depths)) \
               .visuals[0].visual_id
    except StopIteration:
        raise ValueError(
            'Screen does not support depth %d' % depth)


class View:
    """Data class which holds meta data about the screen"""
    def __init__(self):
        self.offset = geometry.Distance()
        self.media = {}


class WindowFactory:
    """Window factory class"""
    def __init__(self, display):
        self.display = display

    @abc.abstractmethod
    def create(self, *window_infos: xutil.TerminalWindowInfo):
        """Creates a child window for each window id."""
        raise NotImplementedError()


class OverlayWindow:
    """Ensures unmapping of windows"""
    SCREEN_DEPTH = 24

    class Factory(WindowFactory):
        """OverlayWindows factory class"""
        def __init__(self, display, view):
            super().__init__(display)
            self.view = view

        def create(self, *window_infos: xutil.TerminalWindowInfo):
            return [OverlayWindow(self.display, self.view, info)
                    for info in window_infos]

    class Placement:
        @attr.s
        class TransformedImage:
            """Data class which contains the options an image was transformed with
            and the image data."""
            options = attr.ib(type=tuple)
            data = attr.ib(type=bytes)

        def __init__(self, x: int, y: int, width: int, height: int,
                     scaling_position: geometry.Point,
                     scaler: scaling.ImageScaler,
                     path: str, image: Image, last_modified: int,
                     cache: weakref.WeakKeyDictionary = None):
            # x, y are useful names in this case
            # pylint: disable=invalid-name
            self.x = x
            self.y = y
            self.width = width
            self.height = height
            self.scaling_position = scaling_position
            self.scaler = scaler
            self.path = path
            self.image = image
            self.last_modified = last_modified
            self.cache = cache or weakref.WeakKeyDictionary()

        def transform_image(self, term_info: xutil.TerminalWindowInfo,
                            width: int, height: int,
                            format_scanline: tuple):
            """Scales to image and calculates the width & height needed to display it.

            Returns:
                tuple of (width: int, height: int, image: bytes)
            """
            scanline_pad, scanline_unit = format_scanline
            transformed_image = self.cache.get(term_info)
            final_size = self.scaler.calculate_resolution(
                self.image, width, height)
            options = self.scaler.get_scaler_name(), final_size

            if (transformed_image is None
                    or transformed_image.options != options):
                image = self.scaler.scale(
                    self.image, self.scaling_position, width, height)
                stride = roundup(image.width * scanline_unit, scanline_pad)
                transformed_image = self.TransformedImage(
                    options, image.tobytes("raw", 'BGRX', stride, 0))
                self.cache[term_info] = transformed_image

            return (*final_size, transformed_image.data)

        def resolve(self, pane_offset: geometry.Distance,
                    term_info: xutil.TerminalWindowInfo,
                    format_scanline):
            """Resolves the position and size of the image
            according to the teminal window information.

            Returns:
                tuple of (x: int, y: int, width: int, height: int,
                          image: PIL.Image)
            """
            # x, y are useful names in this case
            # pylint: disable=invalid-name
            x = int((self.x + pane_offset.left) * term_info.font_width +
                    term_info.padding)
            y = int((self.y + pane_offset.top) * term_info.font_height +
                    term_info.padding)
            width = int(self.width and
                        (self.width * term_info.font_width))
            height = int(self.height and
                         (self.height * term_info.font_height))

            return (x, y, *self.transform_image(
                term_info, width, height, format_scanline))

    def __init__(self, display: Xdisplay.Display,
                 view: View, term_info: xutil.TerminalWindowInfo):
        """Changes the foreground color of the gc object.

        Args:
            display (Xlib.display.Display): any created instance
            parent_id (int): the X11 window id of the parent window
        """
        self._display = display
        self._screen = display.screen()
        self._colormap = None
        self.parent_info = term_info
        self.parent_window = None
        self.window = None
        self._window_gc = None
        self._view = view
        self._width = 1
        self._height = 1
        self._image = Xshm.Image(
            self._screen.width_in_pixels,
            self._screen.height_in_pixels)
        self.create()

    def __enter__(self):
        self.map()
        self.draw()
        return self

    def __exit__(self, *args):
        self.destroy()

    def draw(self):
        """Draws the window and updates the visibility mask."""
        rectangles = []

        scanline_pad = self.window.display.info.bitmap_format_scanline_pad
        scanline_unit = self.window.display.info.bitmap_format_scanline_unit

        for placement in self._view.media.values():
            # x, y are useful names in this case
            # pylint: disable=invalid-name
            x, y, width, height, image = \
                placement.resolve(self._view.offset, self.parent_info,
                                  (scanline_pad, scanline_unit))
            rectangles.append((x, y, width, height))
            self._image.draw(x, y, width, height, image)

        self._image.copy_to(
            self.window.id,
            0, 0, self._width, self._height)
        self.window.shape_rectangles(
            Xshape.SO.Set, Xshape.SK.Bounding, 0,
            0, 0, rectangles)

        self._display.flush()

    def create(self):
        """Creates the window and gc"""
        if self._window_gc:
            return

        visual_id = get_visual_id(self._screen, OverlayWindow.SCREEN_DEPTH)
        self._colormap = self._screen.root.create_colormap(
            visual_id, X.AllocNone)
        self.parent_window = self._display.create_resource_object(
            'window', self.parent_info.window_id)
        parent_size = None
        with xutil.get_display() as display:
            parent_window = display.create_resource_object(
                'window', self.parent_info.window_id)
            parent_size = parent_window.get_geometry()
            self.parent_info.calculate_sizes(
                parent_size.width, parent_size.height)
        self._width, self._height = parent_size.width, parent_size.height

        self.window = self.parent_window.create_window(
            0, 0, parent_size.width, parent_size.height, 0,
            OverlayWindow.SCREEN_DEPTH,
            X.InputOutput,
            visual_id,
            background_pixmap=0,
            colormap=self._colormap,
            background_pixel=0,
            border_pixel=0,
            event_mask=X.ExposureMask)
        self.parent_window.change_attributes(
            event_mask=X.StructureNotifyMask)
        self._window_gc = self.window.create_gc()
        self._set_click_through()
        self._set_invisible()
        self._display.flush()

    def process_event(self, event):
        if (isinstance(event, Xevent.Expose) and
                event.window.id == self.window.id and
                event.count == 0):
            self.draw()
        elif (isinstance(event, Xevent.ConfigureNotify) and
              event.window.id == self.parent_window.id):
            delta_width = event.width - self._width
            delta_height = event.height - self._height

            if delta_width != 0 or delta_height != 0:
                self._width, self._height = event.width, event.height
                self.window.configure(
                    width=event.width,
                    height=event.height)
                self._display.flush()

            if delta_width > 0 or delta_height > 0:
                self.draw()

    def map(self):
        self.window.map()
        self._display.flush()

    def unmap(self):
        self.window.unmap()
        self._display.flush()

    def destroy(self):
        """Destroys the window and it's resources"""
        if self._window_gc:
            self._window_gc.free()
            self._window_gc = None
        if self.window:
            self.window.unmap()
            self.window.destroy()
            self.window = None
        if self._colormap:
            self._colormap.free()
            self._colormap = None
        self._display.flush()

    def _set_click_through(self):
        """Sets the input processing area to an area
        of 1x1 pixel by using the XShape extension.
        So nearly the full window is click-through.
        """
        self.window.shape_rectangles(
            Xshape.SO.Set, Xshape.SK.Input, 0,
            0, 0, [])

    def _set_invisible(self):
        """Makes the window invisible."""
        self.window.shape_rectangles(
            Xshape.SO.Set, Xshape.SK.Bounding, 0,
            0, 0, [])
