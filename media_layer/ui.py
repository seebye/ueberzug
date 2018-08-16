"""This module contains user interface related classes and methods.
"""
import contextlib
import Xlib.X as X
import Xlib.display as Xdisplay
import Xlib.ext.shape as Xshape
import Xlib.protocol.request as Xrequest
import Xlib.protocol.event as Xevent
import PIL.Image as Image


INDEX_ALPHA_CHANNEL = 3


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


def roundup(value, unit):
    # pylint: disable=W,C,R
    # source: https://github.com/python-xlib/python-xlib/blob/8ae15f9e990f64a8adbccf38648057a35b03f531/Xlib/xobject/drawable.py#L834
    return (value + (unit - 1)) & ~(unit - 1)


def put_pil_image(self, gc, x, y, image, onerror=None):
    # pylint: disable=W,C,R
    # hardly modified version of
    # https://github.com/python-xlib/python-xlib/blob/8ae15f9e990f64a8adbccf38648057a35b03f531/Xlib/xobject/drawable.py#L213
    # (forcing it to draw on 32 bit windows,
    # transparent areas will be black
    # we need the shape extension to remove them)
    width, height = image.size
    if image.mode == '1':
        format = X.XYBitmap
        depth = 1
        if self.display.info.bitmap_format_bit_order == 0:
            rawmode = '1;R'
        else:
            rawmode = '1'
        pad = self.display.info.bitmap_format_scanline_pad
        stride = roundup(width, pad) >> 3
    elif image.mode == 'RGB':
        format = X.ZPixmap
        depth = OverlayWindow.SCREEN_DEPTH
        image.convert('RGBA')
        if self.display.info.image_byte_order == 0:
            rawmode = 'BGRX'
        else:
            rawmode = 'RGBX'
        pad = self.display.info.bitmap_format_scanline_pad
        unit = self.display.info.bitmap_format_scanline_unit
        stride = roundup(width * unit, pad) >> 3
    else:
        raise ValueError('Unknown data format ' + image.mode)

    maxlen = (self.display.info.max_request_length << 2) \
             - Xrequest.PutImage._request.static_size
    split = maxlen // stride

    x1 = 0
    x2 = width
    y1 = 0

    while y1 < height:
        h = min(height, split)
        if h < height:
            subimage = image.crop((x1, y1, x2, y1 + h))
        else:
            subimage = image
        w, h = subimage.size
        data = subimage.tobytes("raw", rawmode, stride, 0)
        self.put_image(gc, x, y, w, h, format, depth, 0, data)
        y1 = y1 + h
        y = y + h


def get_image_and_mask(image: Image):
    """Splits the image into the displayed pixels
    and it's opacity mask.

    Args:
        image (Image): PIL.Image instance

    Returns:
        (tuple of Image): (image, mask)
    """
    mask = None

    if image.mode == 'P':
        image = image.convert('RGBA')

    if image.mode in 'RGBA' and len(image.getbands()) == 4:
        image.load()
        image_alpha = image.split()[INDEX_ALPHA_CHANNEL]
        image_rgb = Image.new("RGB", image.size, color=(255, 255, 255))
        mask = Image.new("1", image.size, color=1)
        image_rgb.paste(image, mask=image_alpha)
        mask.paste(0, mask=image_alpha)
        image = image_rgb

    return image, mask


class OverlayWindow:
    """Ensures unmapping of windows"""
    SCREEN_DEPTH = 32

    class Placement:
        def __init__(self, x: int, y: int, image: Image, mask: Image = None):
            # x, y are useful names in this case
            # pylint: disable=invalid-name
            self.x = x
            self.y = y
            self.image = image
            self.mask = mask


    def __init__(self, display: Xdisplay.Display, parent_id: int,
                 placements: dict):
        """Changes the foreground color of the gc object.

        Args:
            display (Xlib.display.Display): any created instance
            parent_id (int): the X11 window id of the parent window
        """
        self._display = display
        self._screen = display.screen()
        self._parent_id = parent_id
        self._colormap = None
        self.parent_window = None
        self.window = None
        self._window_gc = None
        self._placements = placements
        self._width = 1
        self._height = 1
        self.create()

    def __enter__(self):
        self.map()
        return self

    def __exit__(self, *args):
        self.destroy()

    def draw(self):
        """Draws the window and updates the visibility mask."""
        COLOR_INVISIBLE = 0
        COLOR_VISIBLE = 1
        # sometimes get_geometry / ReplyRequests leads to endless waiting..
        '''
        Traceback (most recent call first):
  <built-in method select of module object at remote 0x7fd1481a3b88>
  File "/usr/local/lib/python3.6/dist-packages/Xlib/protocol/display.py", line 562, in send_and_recv
    rs, ws, es = select.select([self.socket], writeset, [], timeout)
  File "/usr/local/lib/python3.6/dist-packages/Xlib/protocol/rq.py", line 1381, in reply
    self._display.send_and_recv(request = self._serial)
  File "/usr/local/lib/python3.6/dist-packages/Xlib/protocol/rq.py", line 1369, in __init__
    self.reply()
  File "/usr/local/lib/python3.6/dist-packages/Xlib/xobject/drawable.py", line 39, in get_geometry
    drawable = self)
  File "/home/nico/Projects/Python/image_layer/image_layer/ui.py", line 161, in draw
    size = self.window.get_geometry()
  File "/home/nico/Projects/Python/image_layer/image_layer/batch.py", line 53, in <listcomp>
    for instance in self.outer]
  File "/home/nico/Projects/Python/image_layer/image_layer/batch.py", line 53, in __call__
    for instance in self.outer]
  File "/home/nico/Projects/Python/image_layer/image_layer/action.py", line 27, in execute
    self.windows.draw()
  File "image_layer/image_layer.py", line 78, in main_commands
---Type <return> to continue, or q <return> to quit---
  File "/usr/lib/python3.6/asyncio/events.py", line 145, in _run
    self._callback(*self._args)
  File "/usr/lib/python3.6/asyncio/base_events.py", line 1434, in _run_once
    handle._run()
  File "/usr/lib/python3.6/asyncio/base_events.py", line 422, in run_forever
    self._run_once()
  File "image_layer/image_layer.py", line 131, in main
  File "image_layer/image_layer.py", line 139, in <module>

  Thread 1 (Thread 0x7fd14858c740 (LWP 9943)):
 557                    if recv or flush:
 558                        timeout = 0
 559                    else:
 560                        timeout = None
 561
>562                    rs, ws, es = select.select([self.socket], writeset, [], timeout)
 563
 564                # Ignore errors caused by a signal recieved while blocking.
 565                # All other errors are re-raised.
 566                except select.error as err:
 567                    if isinstance(err, OSError):
        '''
        # size = self.window.get_geometry()
        mask = None
        mask_gc = None

        try:
            #self.window.clear_area(x=0, y=0, width=self._width, height=self._height)
            mask = self.window.create_pixmap(self._width, self._height, 1)
            mask_gc = mask.create_gc(graphics_exposures=False)

            # make everything invisible
            mask_gc.change(foreground=COLOR_INVISIBLE)
            mask.fill_rectangle(mask_gc, 0, 0, self._width, self._height)

            for placement in self._placements.values():
                #if placement.mask:
                #    mask_gc.change(foreground=COLOR_INVISIBLE)
                #    put_pil_image(mask, mask_gc, placement.x, placement.y, placement.mask)
                #else:
                if True:
                    mask_gc.change(foreground=COLOR_VISIBLE)
                    mask.fill_rectangle(
                        mask_gc, placement.x, placement.y,
                        placement.image.width, placement.image.height)

                put_pil_image(self.window, self._window_gc, placement.x, placement.y, placement.image)

            self.window.shape_mask(
                Xshape.SO.Set, Xshape.SK.Bounding,
                #Xshape.SO.Union, Xshape.SK.Bounding,
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
        self._colormap = self._screen.root.create_colormap(visual_id, X.AllocNone)
        self.parent_window = self._display.create_resource_object('window', self._parent_id)
        parent_size = self.parent_window.get_geometry()
        self._width, self._height = parent_size.width, parent_size.height
        #print('parent', self.parent_window.id)

        self.window = self.parent_window.create_window(
            0, 0, parent_size.width, parent_size.height, 0,
            #0, 0, 1, 1, 0,
            OverlayWindow.SCREEN_DEPTH,
            X.InputOutput,
            visual_id,
            background_pixmap=0,
            colormap=self._colormap,
            background_pixel=0,
            border_pixel=0,
            event_mask=X.ExposureMask)
        #self.window.composite_redirect_subwindows(1)
        #print('window', self.window.id)
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
            #print('target id', event.window.id, event)
            #size = self.window.get_geometry()
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
