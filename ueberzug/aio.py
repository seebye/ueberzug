import select

class LineReader:
    """Async iterator class used to read lines"""

    def __init__(self, loop, file):
        self._loop = loop
        self._file = file

    @staticmethod
    async def read_line(loop, file):
        """Waits asynchronously for a line and returns it"""
        return await loop.run_in_executor(None, file.readline)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if select.select([self._file], [], [], 0)[0]:
            return self._file.readline()
        return await LineReader.read_line(self._loop, self._file)
