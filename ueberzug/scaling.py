"""Modul which implements class and functions
all about scaling images.
"""
import abc
import enum

import PIL.Image as Image

import ueberzug.geometry as geometry


class ImageScaler(metaclass=abc.ABCMeta):
    """Describes the structure used to define image scaler classes.

    Defines a general interface used to implement different ways
    of scaling images to specific sizes.
    """

    @staticmethod
    @abc.abstractmethod
    def get_scaler_name():
        """Returns the constant name which is associated to this scaler."""
        raise NotImplementedError()

    @abc.abstractmethod
    def calculate_resolution(self, image: Image, width: int, height: int):
        """Calculates the final resolution of the scaled image.

        Args:
            image (Image): the image which should be scaled
            width (int): maximum width that can be taken
            height (int): maximum height that can be taken

        Returns:
            tuple: final width: int, final height: int
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def scale(self, image: Image, position: geometry.Point,
              width: int, height: int):
        """Scales the image according to the respective implementation.

        Args:
            image (Image): the image which should be scaled
            position (geometry.Position): the centered position, if possible
                Specified as factor of the image size,
                so it should be an element of [0, 1].
            width (int): maximum width that can be taken
            height (int): maximum height that can be taken

        Returns:
            Image: the scaled image
        """
        raise NotImplementedError()


class OffsetImageScaler(ImageScaler, metaclass=abc.ABCMeta):
    """Extension of the ImageScaler class by Offset specific functions."""
    # pylint can't detect abstract subclasses
    # pylint: disable=abstract-method

    @staticmethod
    def get_offset(position: float, target_size: float, image_size: float):
        """Calculates a offset which contains the position
        in a range from offset to offset + target_size.

        Args:
            position (float): the centered position, if possible
                Specified as factor of the image size,
                so it should be an element of [0, 1].
            target_size (int): the image size of the wanted result
            image_size (int): the image size

        Returns:
            int: the offset
        """
        return int(min(max(0, position * image_size - target_size / 2),
                       image_size - target_size))


class MinSizeImageScaler(ImageScaler):
    """Partial implementation of an ImageScaler.
    Subclasses calculate the final resolution of the scaled image
    as the minimum value of the image size and the maximum size.
    """
    # pylint: disable=abstract-method

    def calculate_resolution(self, image: Image, width: int, height: int):
        return (min(width or image.width, image.width),
                min(height or image.height, image.height))


class CropImageScaler(MinSizeImageScaler, OffsetImageScaler):
    """Implementation of the ImageScaler
    which crops out the maximum image size.
    """

    @staticmethod
    def get_scaler_name():
        return "crop"

    def scale(self, image: Image, position: geometry.Point,
              width: int, height: int):
        width, height = self.calculate_resolution(image, width, height)
        image_width, image_height = image.width, image.height
        offset_x = self.get_offset(position.x, width, image_width)
        offset_y = self.get_offset(position.y, height, image_height)
        return image \
            .crop((offset_x, offset_y,
                   offset_x + width, offset_y + height))


class DistortImageScaler(ImageScaler):
    """Implementation of the ImageScaler
    which distorts the image to the maximum image size.
    """

    @staticmethod
    def get_scaler_name():
        return "distort"

    def calculate_resolution(self, image: Image, width: int, height: int):
        return width or image.width, height or image.height

    def scale(self, image: Image, position: geometry.Point,
              width: int, height: int):
        width, height = self.calculate_resolution(image, width, height)
        return image.resize((width, height), Image.ANTIALIAS)


class ContainImageScaler(DistortImageScaler):
    """Implementation of the ImageScaler
    which resizes the image to a size <= the maximum size
    while keeping the image ratio.
    """

    @staticmethod
    def get_scaler_name():
        return "contain"

    def calculate_resolution(self, image: Image, width: int, height: int):
        image_width, image_height = image.width, image.height

        if (width and width < image_width):
            image_height = image_height * width / image_width
            image_width = width
        if (height and height < image_height):
            image_width = image_width * height / image_height
            image_height = height

        return int(image_width), int(image_height)


class ForcedCoverImageScaler(DistortImageScaler, OffsetImageScaler):
    """Implementation of the ImageScaler
    which resizes the image to cover the entire area which should be filled
    while keeping the image ratio.
    If the image is smaller than the desired size
    it will be stretched to reach the desired size.
    If the ratio of the area differs
    from the image ratio the edges will be cut off.
    """

    @staticmethod
    def get_scaler_name():
        return "forced_cover"

    def scale(self, image: Image, position: geometry.Point,
              width: int, height: int):
        width, height = self.calculate_resolution(image, width, height)
        image_width, image_height = image.width, image.height
        if width / image_width > height / image_height:
            image_height = int(image_height * width / image_width)
            image_width = width
        else:
            image_width = int(image_width * height / image_height)
            image_height = height
        offset_x = self.get_offset(position.x, width, image_width)
        offset_y = self.get_offset(position.y, height, image_height)

        return image \
            .resize((image_width, image_height), Image.ANTIALIAS) \
            .crop((offset_x, offset_y,
                   offset_x + width, offset_y + height))


class CoverImageScaler(MinSizeImageScaler, ForcedCoverImageScaler):
    """The same as ForcedCoverImageScaler but images won't be stretched
    if they are smaller than the area which should be filled.
    """

    @staticmethod
    def get_scaler_name():
        return "cover"


@enum.unique
class ScalerOption(str, enum.Enum):
    """Enum which lists the useable ImageScaler classes."""
    DISTORT = DistortImageScaler
    CROP = CropImageScaler
    CONTAIN = ContainImageScaler
    FORCED_COVER = ForcedCoverImageScaler
    COVER = CoverImageScaler

    def __new__(cls, scaler_class):
        inst = str.__new__(cls)
        # Based on an official example
        # https://docs.python.org/3/library/enum.html#using-a-custom-new
        # So.. stfu pylint
        # pylint: disable=protected-access
        inst._value_ = scaler_class.get_scaler_name()
        inst.scaler_class = scaler_class
        return inst
