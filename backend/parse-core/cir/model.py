from dataclasses import dataclass
from typing import Literal, Optional, Tuple

Visibility = Literal["public", "protected", "private", "package"]

@dataclass
class TypeDecl:
    id: str
    name: str
    kind: Literal["class", "interface", "enum"]
    visibility: Visibility = "package"
    package: Optional[str] = None
    modifiers: Tuple[str, ...] = ()
    is_abstract: bool = False
    is_final: bool = False

@dataclass
class Field:
    id: str
    name: str
    type_name: str            # logical element type (e.g. Item)
    raw_type: str             # raw type text (e.g. List<Item>)
    visibility: Visibility = "package"
    modifiers: Tuple[str, ...] = ()
    multiplicity: Optional[str] = None  # e.g. "1", "0..*", "1..*"

@dataclass
class Method:
    id: str
    name: str
    return_type: str          # logical type
    raw_return_type: str      # raw type text
    visibility: Visibility = "package"
    modifiers: Tuple[str, ...] = ()
    is_constructor: bool = False
    is_static: bool = False
    is_abstract: bool = False
    is_final: bool = False

@dataclass
class Parameter:
    id: str
    name: str
    type_name: str            # logical element type
    raw_type: str             # raw type text
