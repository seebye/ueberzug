import subprocess
import os


def is_used():
    """Determines whether this program runs in tmux or not."""
    return get_pane() is not None


def get_pane():
    """Determines the pane identifier this process runs in.
    Returns:
        str or None
    """
    return os.environ.get('TMUX_PANE')


def is_window_focused():
    """Determines whether the window
    which owns the pane
    which owns this process is focused.
    """
    result = subprocess.check_output([
        'tmux', 'display', '-p',
        '-F', '#{window_active}',
        '-t', get_pane()
    ]).decode()
    return result == "1\n"


def get_clients():
    """Determines each tmux client
    displaying the pane this program runs in.
    """
    return [int(pid) for pid in
            subprocess.check_output([
                'tmux', 'list-clients',
                '-F', '#{client_pid}',
                '-t', get_pane()
            ]).decode().splitlines()]


def get_client_ttys_by_pid():
    """Determines the tty for each tmux client
    displaying the pane this program runs in.
    """
    if not is_window_focused():
        return {}

    return {int(pid): tty
            for pid_tty in
            subprocess.check_output([
                'tmux', 'list-clients',
                '-F', '#{client_pid},#{client_tty}',
                '-t', get_pane()
            ]).decode().splitlines()
            for pid, tty in (pid_tty.split(','),)}
