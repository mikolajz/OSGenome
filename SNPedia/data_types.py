from enum import Enum
from typing import NewType

Rsid = NewType('Rsid', str)


class Orientation(Enum):
    PLUS = "plus"
    MINUS = "minus"
