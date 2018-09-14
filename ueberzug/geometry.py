"""Module which defines classes all about geometry"""


class Distance:
    """Data class which holds the distance values in all directions."""
    def __init__(self, top=0, left=0, bottom=0, right=0):
        self.top = top
        self.left = left
        self.bottom = bottom
        self.right = right
