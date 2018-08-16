"""This module contains x11 utils"""
import os
import subprocess
import Xlib
import Xlib.display as Xdisplay
import psutil

ENV_KEY_TMUX_PANE = 'TMUX_PANE'
ENV_KEY_WINDOW_ID = 'WINDOWID'


class Events:
    """Async iterator class for x11 events"""

    def __init__(self, loop, display: Xdisplay.Display):
        self._loop = loop
        self._display = display

    @staticmethod
    async def receive_event(loop, display):
        """Waits asynchronously for an x11 event and returns it"""
        return await loop.run_in_executor(None, display.next_event)

    async def __aiter__(self):
        return self

    async def __anext__(self):
        return await Events.receive_event(self._loop, self._display)


def get_parent_pids(pid=None):
    pids = []
    process = psutil.Process(pid=pid)

    while (process is not None and
           process.pid > 1):
        pids.append(process.pid)
        process = process.parent()

    return pids


def get_tmux_clients(target):
    """Determines each tmux client
    displaying the pane this program runs in.
    """
    return [int(pid) for pid in
            subprocess.check_output([
                'tmux', 'list-clients',
                '-F', '#{client_pid}',
                '-t', target
            ]).decode().splitlines()]


def get_first_window_id(display: Xdisplay.Display, pids):
    """Determines the window id of the youngest
    parent owning a window.
    """
    root = display.screen().root
    win_ids_res = [None] * len(pids)
    win_ids = root.get_full_property(display.intern_atom('_NET_CLIENT_LIST'),
                                     Xlib.X.AnyPropertyType).value
    for window_id in win_ids:
        window = display.create_resource_object('window', window_id)
        prop = window.get_full_property(display.intern_atom('_NET_WM_PID'), Xlib.X.AnyPropertyType)
        pid = prop.value[0]

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


def get_parent_window_ids(display: Xdisplay.Display):
    """Determines the window id of each
    terminal which displays the program using
    this layer.
    """
    window_ids = []
    client_pids = []
    tmux_pane = os.environ.get(ENV_KEY_TMUX_PANE)
    environ_window_id = os.environ.get(ENV_KEY_WINDOW_ID)

    if tmux_pane is not None:
        client_pids = get_tmux_clients(tmux_pane)
    elif environ_window_id is not None:
        window_ids.append(int(environ_window_id))
    else:
        client_pids = [psutil.Process().pid]

    for pid in client_pids:
        wid = get_first_window_id(display, get_parent_pids(pid))
        if wid:
            window_ids.append(wid)

    return window_ids
