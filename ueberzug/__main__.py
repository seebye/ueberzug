#!/usr/bin/env python3
"""Usage:
    ueberzug layer [options]
    ueberzug library
    ueberzug version
    ueberzug query_windows PIDS ...

Routines:
    layer                   Display images
    library                 Prints the path to the bash library
    version                 Prints the project version
    query_windows           Orders ueberzug to search for windows.
                            Only for internal use.

Layer options:
    -p, --parser <parser>  one of json, simple, bash
                           json: Json-Object per line
                           simple: Key-Values separated by a tab
                           bash: associative array dumped via `declare -p`
                           [default: json]
    -l, --loader <loader>  one of synchronous, thread, process
                           synchronous: load images right away
                           thread: load images in threads
                           process: load images in additional processes
                           [default: thread]
    --window-id <id>       set the window id that the layer will displays on,
                           to disambiguate pid that contains multiple windows
    -s, --silent           print stderr to /dev/null


License:
    ueberzug  Copyright (C) 2018  Nico Baeurer
    This program comes with ABSOLUTELY NO WARRANTY.
    This is free software, and you are welcome to redistribute it
    under certain conditions.
"""
import docopt


def main():
    options = docopt.docopt(__doc__)
    module = None

    if options['layer']:
        import ueberzug.layer as layer
        module = layer
    elif options['library']:
        import ueberzug.library as library
        module = library
    elif options['query_windows']:
        import ueberzug.query_windows as query_windows
        module = query_windows
    elif options['version']:
        import ueberzug.version as version
        module = version

    module.main(options)


if __name__ == '__main__':
    main()
