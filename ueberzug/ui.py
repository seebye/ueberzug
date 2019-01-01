"""This module contains user interface related classes and methods.
"""
import abc

import Xlib.X as X
import Xlib.display as Xdisplay
import Xlib.ext.shape as Xshape
import Xlib.protocol.event as Xevent
import PIL.Image as Image
import PIL.ImageDraw as ImageDraw
import PIL.ImageFont as ImageFont

import ueberzug.xutil as xutil
import ueberzug.geometry as geometry


class UnsupportedException(Exception):
    """Exception thrown for unsupported operations."""
    pass


def get_visual_id(screen, depth: int):
    """Determines the visual id
    for the given screen and - depth.
    """
    try:
        return next(filter(lambda i: i.depth == depth,
                           screen.allowed_depths)) \
               .visuals[0].visual_id
    except StopIteration:
        raise UnsupportedException(
            'Screen does not support %d depth' % depth)


def add_overlay_text(image: Image, x: int, y: int, text: str,
                     foreground=(255, 255, 255),
                     background=(0, 0, 0)):
    """Draws a text over an image."""
    default_font = ImageFont.load_default()
    width, height = default_font.getsize(text)
    draw = ImageDraw.Draw(image)
    draw.rectangle(((x, y), (x + width, y + height)), background)
    draw.text((x, y), text, foreground, default_font)


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
        def __init__(self, x: int, y: int, width: int, height: int,
                     max_width: int, max_height: int,
                     image: Image):
            # x, y are useful names in this case
            # pylint: disable=invalid-name
            self.x = x
            self.y = y
            self.width = width
            self.max_width = max_width
            self.height = height
            self.max_height = max_height
            self.image = image

        def resolve(self, pane_offset: geometry.Distance,
                    term_info: xutil.TerminalWindowInfo):
            """Resolves the position and size of the image
            according to the teminal window information.

            Returns:
                tuple of (x: int, y: int, width: int, height: int,
                          resized_image: PIL.Image)
            """
            # x, y are useful names in this case
            # pylint: disable=invalid-name
            x = ((self.x + pane_offset.left) * term_info.font_width +
                 term_info.padding)
            y = ((self.y + pane_offset.top) * term_info.font_height +
                 term_info.padding)
            width = (self.width * term_info.font_width
                     if self.width
                     else self.image.width)
            height = (self.height * term_info.font_height
                      if self.height
                      else self.image.height)
            max_width = (self.max_width and
                         (self.max_width * term_info.font_width))
            max_height = (self.max_height and
                          (self.max_height * term_info.font_height))

            if (max_width and max_width < width):
                height = height * max_width / width
                width = max_width
            if (max_height and max_height < height):
                width = width * max_height / height
                height = max_height

            image = self.image.resize((int(width), int(height)),
                                      Image.ANTIALIAS)

            return int(x), int(y), int(width), int(height), image

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
        self.create()

    def __enter__(self):
        self.map()
        self.draw()
        return self

    def __exit__(self, *args):
        self.destroy()

    def draw(self):
        """Draws the window and updates the visibility mask."""
        COLOR_INVISIBLE = 0
        COLOR_VISIBLE = 1
        mask = None
        mask_gc = None

        try:
            mask = self.window.create_pixmap(self._width, self._height, 1)
            mask_gc = mask.create_gc(graphics_exposures=False)

            # make everything invisible
            mask_gc.change(foreground=COLOR_INVISIBLE)
            mask.fill_rectangle(mask_gc, 0, 0, self._width, self._height)

            for placement in self._view.media.values():
                # x, y are useful names in this case
                # pylint: disable=invalid-name
                x, y, width, height, image = \
                        placement.resolve(self._view.offset, self.parent_info)

                mask_gc.change(foreground=COLOR_VISIBLE)
                mask.fill_rectangle(mask_gc, x, y, width, height)

                if not self._view.offset.left == self._view.offset.top == 0:
                    add_overlay_text(
                        image, 0, 0,
                        "Multi pane windows aren't supported")

                self.window.put_pil_image(
                    self._window_gc, x, y, image)

            self.window.shape_mask(
                Xshape.SO.Set, Xshape.SK.Bounding,
                0, 0, mask)
        finally:
            if mask_gc:
                mask_gc.free()
            if mask:
                mask.free()

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
        mask = None

        try:
            mask = self.window.create_pixmap(1, 1, 1)
            self.window.shape_mask(
                Xshape.SO.Set, Xshape.SK.Input,
                0, 0, mask)
        finally:
            if mask:
                mask.free()

    def _set_invisible(self):
        """Makes the window invisible."""
        mask = None

        try:
            mask = self.window.create_pixmap(1, 1, 1)
            self.window.shape_mask(
                Xshape.SO.Set, Xshape.SK.Bounding,
                0, 0, mask)
        finally:
            if mask:
                mask.free()
