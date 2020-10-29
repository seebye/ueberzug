import os
import signal
import errno


def get_command(pid):
    """Figures out the associated command name
    of a process with the given pid.

    Args:
        pid (int): the pid of the process of interest

    Returns:
        str: the associated command name
    """
    with open('/proc/{}/comm'.format(pid), 'r') as commfile:
        return '\n'.join(commfile.readlines())


def is_same_command(pid0, pid1):
    """Checks whether the associated command name
    of the processes of the given pids equals to each other.

    Args:
        pid0 (int): the pid of the process of interest
        pid1 (int): the pid of another process of interest

    Returns:
        bool: True if both processes have
              the same associated command name
    """
    return get_command(pid0) == get_command(pid1)


def send_signal_safe(own_pid, target_pid):
    """Sends SIGUSR1 to a process if both
    processes have the same associated command name.
    (Race condition free)

    Requires:
        - Python 3.9+
        - Linux 5.1+

    Args:
        own_pid (int): the pid of this process
        target_pid (int):
            the pid of the process to send the signal to
    """
    pidfile = None
    try:
        pidfile = os.pidfile_open(target_pid)
        if is_same_command(own_pid, target_pid):
            signal.pidfd_send_signal(pidfile, signal.SIGUSR1)
    except FileNotFoundError:
        pass
    except OSError as error:
        # not sure if errno is really set..
        # at least the documentation of the used functions says so..
        # see e.g.: https://github.com/python/cpython/commit/7483451577916e693af6d20cf520b2cc7e2174d2#diff-99fb04b208835118fdca0d54b76a00c450da3eaff09d2b53e8a03d63bbe88e30R1279-R1281
        # and https://docs.python.org/3/c-api/exceptions.html#c.PyErr_SetFromErrno

        # caused by either pidfile_open or pidfd_send_signal
        if error.errno != errno.ESRCH:
            raise
        # else: the process is death
    finally:
        if pidfile is not None:
            os.close(pidfile)


def send_signal_unsafe(own_pid, target_pid):
    """Sends SIGUSR1 to a process if both
    processes have the same associated command name.
    (Race condition if process dies)

    Args:
        own_pid (int): the pid of this process
        target_pid (int):
            the pid of the process to send the signal to
    """
    try:
        if is_same_command(own_pid, target_pid):
            os.kill(target_pid, signal.SIGUSR1)
    except (FileNotFoundError, ProcessLookupError):
        pass


def main(options):
    # assumption:
    # started by calling the programs name
    # ueberzug layer and
    # ueberzug query_windows
    own_pid = os.getpid()

    for pid in options['PIDS']:
        try:
            send_signal_safe(own_pid, int(pid))
        except AttributeError:
            send_signal_unsafe(own_pid, int(pid))
