"""This module contains x11 utils"""
import os
import functools
import asyncio

import Xlib
import Xlib.display as Xdisplay
import psutil

import ueberzug.tmux_util as tmux_util
import ueberzug.terminal as terminal


Xdisplay.Display.__enter__ = lambda self: self
Xdisplay.Display.__exit__ = lambda self, *args: self.close()

PREPARED_DISPLAYS = []
DISPLAY_SUPPLIES = 5

class Events:
    """Async iterator class for x11 events"""

    def __init__(self, loop, display: Xdisplay.Display):
        self._loop = loop
        self._display = display

    @staticmethod
    async def receive_event(loop, display):
        """Waits asynchronously for an x11 event and returns it"""
        return await loop.run_in_executor(None, display.next_event)

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await Events.receive_event(self._loop, self._display)


class TerminalWindowInfo(terminal.TerminalInfo):
    def __init__(self, window_id, fd_pty=None):
        self.window_id = window_id
        super().__init__(window_id,fd_pty)


async def prepare_display():
    """Fills up the display supplies."""
    PREPARED_DISPLAYS.append(Xdisplay.Display())


def get_display():
    """Unfortunately, Xlib tends to produce death locks
    on request with an expected reply.
    (e.g. Drawable#get_geometry)
    Use for each request a new display as workaround.
    """
    for i in range(len(PREPARED_DISPLAYS) - 1, DISPLAY_SUPPLIES):
        asyncio.ensure_future(prepare_display())
    if not PREPARED_DISPLAYS:
        return Xdisplay.Display()
    return PREPARED_DISPLAYS.pop()


@functools.lru_cache()
def get_parent_pids(pid=None):
    pids = []
    process = psutil.Process(pid=pid)

    while (process is not None and
           process.pid > 1):
        pids.append(process.pid)
        process = process.parent()

    return pids


def get_pid_by_window_id(display: Xdisplay.Display, window_id: int):
    window = display.create_resource_object('window', window_id)
    prop = window.get_full_property(display.intern_atom('_NET_WM_PID'), Xlib.X.AnyPropertyType)
    return prop.value[0]


def get_pid_window_id_map():
    """Determines the pid of each mapped window.

    Returns:
        dict of {pid: window_id}
    """
    with get_display() as display:
        root = display.screen().root
        win_ids = root.get_full_property(display.intern_atom('_NET_CLIENT_LIST'),
                                         Xlib.X.AnyPropertyType).value

        return {
            get_pid_by_window_id(display, window_id): window_id
            for window_id in win_ids
        }


def get_first_window_id(pid_window_id_map: dict, pids: list):
    """Determines the window id of the youngest
    parent owning a window.
    """
    win_ids_res = [None] * len(pids)

    for pid, window_id in pid_window_id_map.items():
        try:
            win_ids_res[pids.index(pid)] = window_id
        except ValueError:
            pass

    try:
        return next(i for i in win_ids_res if i)
    except StopIteration:
        # Window needs to be mapped,
        # otherwise it's not listed in _NET_CLIENT_LIST
        return None


def get_parent_window_infos():
    """Determines the window id of each
    terminal which displays the program using
    this layer.

    Returns:
        list of TerminalWindowInfo
    """
    window_infos = []
    clients_pid_tty = {}
    environ_window_id = os.environ.get('WINDOWID')

    if tmux_util.is_used():
        clients_pid_tty = tmux_util.get_client_ttys_by_pid()
    elif environ_window_id is not None:
        window_infos.append(TerminalWindowInfo(int(environ_window_id)))
    else:
        clients_pid_tty = {psutil.Process().pid: None}

    if clients_pid_tty:
        pid_window_id_map = get_pid_window_id_map()

        for pid, pty in clients_pid_tty.items():
            wid = get_first_window_id(pid_window_id_map,
                                      get_parent_pids(pid))
            if wid:
                window_infos.append(TerminalWindowInfo(wid, pty))

    return window_infos
