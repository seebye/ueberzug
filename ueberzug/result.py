import sys

import ueberzug.parser as parser


class Result(dict):
    """Describes the structure used to define result classes.

    Defines a general interface used to implement
    the structure and transfer of a result of a executed command.
    """

    def print(self, parser_object: parser.Parser):
        """Prints the result to stderr.

        Args:
            parser_object (parser.Parser):
                the parser object used to format the result
        """
        print(parser_object.unparse(self),
              file=sys.stderr)


class ErrorResult(Result):
    """Implements the result of commands which
    ran into problems during their execution.

    More clear: an exception was raised.
    """

    def __init__(self, error: Exception):
        super().__init__()
        self.update({
            'type': 'error',
            'name': type(error).__name__,
            'message': str(error),
            # 'stack': traceback.format_exc()
        })
