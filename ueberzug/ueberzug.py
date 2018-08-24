#!/usr/bin/env python3
"""Usage:
    ueberzug ROUTINE [options]

Routines:
    image                   Display images
    library                 Print bash library path

Image options:
    -p, --parser <parser>  one of json, simple, bash
                           json: Json-Object per line
                           simple: Key-Values separated by a tab
                           bash: associative array dumped via `declare -p`
                           [default: json]


License:
    ueberzug  Copyright (C) 2018  Nico Baeurer
    This program comes with ABSOLUTELY NO WARRANTY.
    This is free software, and you are welcome to redistribute it
    under certain conditions.
"""
import atexit
import sys
import os
import asyncio
import signal
import functools
import concurrent.futures as futures
import pathlib
import traceback

import docopt
import Xlib.display as Xdisplay

import ueberzug.aio as aio
import ueberzug.xutil as xutil
import ueberzug.parser as parser
import ueberzug.ui as ui
import ueberzug.batch as batch
import ueberzug.action as action


async def main_xevents(loop, display, windows):
    """Coroutine which processes X11 events"""
    async for event in xutil.Events(loop, display):
        if windows:
            windows.process_event(event)


async def main_commands(loop, shutdown_routine, parser_object,
                        window_factory, windows, media):
    """Coroutine which processes the input of stdin"""
    async for line in aio.LineReader(loop, sys.stdin):
        if not line:
            asyncio.ensure_future(shutdown_routine)
            break

        try:
            data = parser_object.parse(line[:-1])
            command = action.Command(data.pop('action')) #pylint: disable=E1120
            command.action_class(window_factory, windows, media) \
                    .execute(**data)
        except (parser.ParseError, KeyError, ValueError, TypeError) as error:
            cause = (error.args[0]
                     if isinstance(error, parser.ParseError)
                     else error)
            print(parser_object.unparse({
                'type': 'error',
                'name': type(cause).__name__,
                'message': str(error),
                #'stack': traceback.format_exc()
            }), file=sys.stderr)


async def shutdown(loop):
    tasks = [task for task in asyncio.Task.all_tasks() if task is not
             asyncio.tasks.Task.current_task()]
    list(map(lambda task: task.cancel(), tasks))
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()


def main_image(options):
    display = xutil.get_display()
    window_infos = xutil.get_parent_window_infos()
    loop = asyncio.get_event_loop()
    executor = futures.ThreadPoolExecutor(max_workers=2)
    shutdown_routine = shutdown(loop) #pylint: disable=E1111
    parser_class = parser.ParserOption(options['--parser']).parser_class
    media = {}
    window_factory = ui.OverlayWindow.Factory(display, media)
    windows = batch.BatchList(window_factory.create(*window_infos))

    with windows:
        # this could lead to unexpected behavior,
        # but hey otherwise it breaks exiting the script..
        # as readline for example won't return till a line was read
        # and there's no (already integrated) way to
        # disable it only for a specific threadpoolexecutor
        # see: https://github.com/python/cpython/blob/master/Lib/concurrent/futures/thread.py#L33
        # -> TODO: reimplement ThreadPoolExecutor
        atexit.unregister(futures.thread._python_exit) #pylint: disable=W0212
        loop.set_default_executor(executor)

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                functools.partial(asyncio.ensure_future, shutdown_routine))

        asyncio.ensure_future(main_xevents(loop, display, windows))
        asyncio.ensure_future(main_commands(
            loop, shutdown_routine, parser_class(),
            window_factory, windows, media))

        try:
            loop.run_forever()
        finally:
            loop.close()
            executor.shutdown(wait=False)


def main_library():
    directory = pathlib.PosixPath(os.path.abspath(os.path.dirname(__file__))) / 'libs'
    print((directory / 'lib.sh').as_posix())


def main():
    options = docopt.docopt(__doc__)
    routine = options['ROUTINE'] 

    if routine == 'image':
        main_image(options)
    elif routine == 'library':
        main_library()


if __name__ == '__main__':
    main()
