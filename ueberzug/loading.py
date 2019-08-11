import abc
import queue
import weakref
import os
import threading
import concurrent.futures

import PIL.Image
import ueberzug.thread as thread


def load_image(path):
    """Loads the image and converts it
    if it doesn't use the RGB or RGBX mode.

    Args:
        path (str): the path of the image file

    Returns:
        PIL.Image: rgb image

    Raises:
        OSError: for unsupported formats
    """
    image = PIL.Image.open(path)
    image.load()
    if image.mode not in ('RGB', 'RGBX'):
        image_rgb = PIL.Image.new(
            "RGB", image.size, color=(255, 255, 255))
        image_rgb.paste(image)
        image = image_rgb
    return image


class ImageHolder:
    """Holds the reference of an image.
    It serves as bridge between image loader and image user.
    """
    def __init__(self, path, image=None):
        self.path = path
        self.image = image
        self.waiter = threading.Condition()

    def reveal_image(self, image):
        """Assigns an image to this holder and
        notifies waiting image users about it.

        Args:
            image (PIL.Image): the loaded image
        """
        with self.waiter:
            self.image = image
            self.waiter.notify_all()

    def await_image(self):
        """Waits till an image loader assigns the image
        if it's not already happened.

        Returns:
            PIL.Image: the image assigned to this holder
        """
        if self.image is None:
            with self.waiter:
                if self.image is None:
                    self.waiter.wait()
        return self.image


class ImageLoader(metaclass=abc.ABCMeta):
    """Describes the structure used to define image loading strategies.

    Defines a general interface used to implement different ways
    of loading images.
    E.g. loading images asynchron
    """
    PLACEHOLDER = PIL.Image.new('RGB', (1, 1))

    def __init__(self):
        self.error_handler = None

    @abc.abstractmethod
    def load(self, path):
        """Starts the image loading procedure for the passed path.
        How and when an image get's loaded depends on the implementation
        of the used ImageLoader class.

        Args:
            path (str): the path to the image which should be loaded

        Returns:
            ImageHolder: which the image will be assigned to
        """
        raise NotImplementedError()

    def register_error_handler(self, error_handler):
        """Set's the error handler to the passed function.
        An error handler will be called with exceptions which were
        raised during loading an image.

        Args:
            error_handler (Function(Exception)):
                the function which should be called
                to handle an error
        """
        self.error_handler = error_handler

    def process_error(self, exception):
        """Processes an exception.
        Calls the error_handler with the exception
        if there's any.

        Args:
            exception (Exception): the occurred error
        """
        if self.error_handler is not None:
            self.error_handler(exception)


class SynchronImageLoader(ImageLoader):
    """Implementation of ImageLoader
    which loads images right away in the same thread
    it was requested to load the image.
    """
    def load(self, path):
        image = None

        try:
            image = load_image(path)
        except OSError as exception:
            self.process_error(exception)

        return ImageHolder(path, image or self.PLACEHOLDER)


class AsynchronImageLoader(ImageLoader):
    """Extension of ImageLoader
    which adds basic functionality
    needed to implement asynchron image loading.
    """
    def __init__(self):
        super().__init__()
        self.__queue = queue.Queue()

    def _enqueue(self, image_holder):
        """Enqueues the image holder weakly referenced.

        Args:
            image_holder (ImageHolder):
                the image holder for which an image should be loaded
        """
        self.__queue.put(weakref.ref(image_holder))

    def _dequeue(self):
        """Removes queue entries till an alive reference was found.
        The referenced image holder will be returned in this case.
        Otherwise if there wasn't found any alive reference
        None will be returned.

        Returns:
            ImageHolder: an queued image holder or None
        """
        holder_reference = None
        image_holder = None

        while True:
            holder_reference = self.__queue.get_nowait()
            image_holder = holder_reference and holder_reference()
            if (holder_reference is None or
                    image_holder is not None):
                break

        return image_holder


# * Pythons GIL limits the usefulness of threads.
# So in order to use all cpu cores (assumed GIL isn't released)
# you need to use multiple processes.
# * Pillows load method will read & decode the image.
# So it does the I/O and CPU work.
# Decoding seems to be the bottleneck for large images.
# * Using multiple processes comes with it's own bottleneck
# (transfering the data between the processes).
#
# => Using multiple processes seems to be faster for small images.
#    Using threads seems to be faster for large images.
class ProcessImageLoader(AsynchronImageLoader):
    """Implementation of AsynchronImageLoader
    which loads images in multiple processes.
    Therefore it allows to utilise all cpu cores
    for decoding an image.
    """
    def __init__(self):
        super().__init__()
        cpu_cores = os.cpu_count()
        self.__executor_chooser = thread.DaemonThreadPoolExecutor(
            max_workers=cpu_cores)
        self.__executor_loader = concurrent.futures.ProcessPoolExecutor(
            max_workers=cpu_cores)
        # ProcessPoolExecutor won't work
        # when used first in ThreadPoolExecutor
        self.__executor_loader \
            .submit(id, id) \
            .result()

    def load(self, path):
        holder = ImageHolder(path)
        self._enqueue(holder)
        self.__executor_chooser.submit(self.__process_queue)
        return holder

    def __process_queue(self):
        """Processes a single queued entry."""
        image = None
        image_holder = self._dequeue()
        if image_holder is None:
            return

        try:
            future = (self.__executor_loader
                      .submit(load_image, image_holder.path))
            image = future.result()
        except OSError as exception:
            self.process_error(exception)
        finally:
            image_holder.reveal_image(image or self.PLACEHOLDER)


class ThreadImageLoader(AsynchronImageLoader):
    """Implementation of AsynchronImageLoader
    which loads images in multiple threads.
    """
    def __init__(self):
        super().__init__()
        cpu_cores = os.cpu_count()
        self.__executor = thread.DaemonThreadPoolExecutor(
            max_workers=cpu_cores)

    def load(self, path):
        holder = ImageHolder(path)
        self._enqueue(holder)
        self.__executor.submit(self.__process_queue)
        return holder

    def __process_queue(self):
        """Processes a single queued entry."""
        image = None
        image_holder = self._dequeue()
        if image_holder is None:
            return

        try:
            image = load_image(image_holder.path)
        except OSError as exception:
            self.process_error(exception)
        finally:
            image_holder.reveal_image(image or self.PLACEHOLDER)
