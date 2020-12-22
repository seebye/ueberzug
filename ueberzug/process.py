import re
import os
import functools


MAX_PROCESS_NAME_LENGTH = 15
MINOR_DEVICE_NUMBER_MASK = 0b1111_1111_1111_0000_0000_0000_1111_1111


@functools.wraps(os.getpid)
def get_own_pid(*args, **kwargs):
    # pylint: disable=missing-docstring
    return os.getpid(*args, **kwargs)


def get_info(pid: int):
    """Determines information about the process with the given pid.

    Determines
    - the process id (pid)
    - the command name (comm)
    - the state (state)
    - the process id of the parent process (ppid)
    - the process group id (pgrp)
    - the session id (session)
    - the controlling terminal (tty_nr)
    of the process with the given pid.

    Args:
        pid (int or str):
            the associated pid of the process
            for which to retrieve the information for

    Returns:
        dict of str: bytes:
            containing the listed information.
            The term in the brackets is used as key.

    Raises:
        FileNotFoundError: if there is no process with the given pid
    """
    with open(f'/proc/{pid}/stat', 'rb') as proc_file:
        data = proc_file.read()
        return (
            re.search(
                rb'^(?P<pid>[-+]?\d+) '
                rb'\((?P<comm>.{0,' +
                str(MAX_PROCESS_NAME_LENGTH).encode() + rb'})\) '
                rb'(?P<state>.) '
                rb'(?P<ppid>[-+]?\d+) '
                rb'(?P<pgrp>[-+]?\d+) '
                rb'(?P<session>[-+]?\d+) '
                rb'(?P<tty_nr>[-+]?\d+)', data)
            .groupdict())


@functools.lru_cache()
def get_pty_slave_folders():
    """Determines the folders in which linux
    creates the control device files of the pty slaves.

    Returns:
        list of str: containing the paths to these folders
    """
    paths = []

    with open('/proc/tty/drivers', 'rb') as drivers_file:
        for line in drivers_file:
            # The documentation about /proc/tty/drivers
            # is a little bit short (man proc):
            # /proc/tty
            #     Subdirectory containing the pseudo-files and
            #     subdirectories for tty drivers and line disciplines.
            # So.. see the source code:
            # https://github.com/torvalds/linux/blob/8653b778e454a7708847aeafe689bce07aeeb94e/fs/proc/proc_tty.c#L28-L67
            driver = (
                re.search(
                    rb'^(?P<name>(\S| )+?) +'
                    rb'(?P<path>/dev/\S+) ',
                    line)
                .groupdict())
            if driver['name'] == b'pty_slave':
                paths += [driver['path'].decode()]

    return paths


def get_parent_pid(pid: int):
    """Determines pid of the parent process of the process with the given pid.

    Args:
        pid (int or str):
            the associated pid of the process
            for which to retrieve the information for

    Returns:
        int: the pid of the parent process

    Raises:
        FileNotFoundError: if there is no process with the given pid
    """
    process_info = get_info(pid)
    return int(process_info['ppid'])


def get_pty_slave(pid: int):
    """Determines control device file
    of the pty slave of the process with the given pid.

    Args:
        pid (int or str):
            the associated pid of the process
            for which to retrieve the information for

    Returns:
        str or None:
            the path to the control device file
            or None if no path was found

    Raises:
        FileNotFoundError: if there is no process with the given pid
    """
    pty_slave_folders = get_pty_slave_folders()
    process_info = get_info(pid)
    tty_nr = int(process_info['tty_nr'])
    minor_device_number = tty_nr & MINOR_DEVICE_NUMBER_MASK

    for folder in pty_slave_folders:
        device_path = f'{folder}/{minor_device_number}'

        if tty_nr == os.stat(device_path).st_rdev:
            return device_path

    return None
