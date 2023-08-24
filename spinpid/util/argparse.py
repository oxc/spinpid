from typing import Type, TypeVar, Callable, Union
from enum import Enum
import argparse

EnumType = Type[Enum]
E = TypeVar('E', bound=EnumType)


def enum_parser(enum: E) -> Callable[[Union[int, str]], E]:
    def parse(value):
        if isinstance(value, int):
            return enum(value)
        else:
            return enum[value]

    return parse


def enum_choices(enum: EnumType) -> str:
    return ', '.join(str(choice) for k, v in enum.__members__.items() for choice in (k, v.value))


def enum_metavar(enum: EnumType) -> str:
    return "{%s}" % ','.join(enum.__members__.keys())


def add_enum_argument(parser, *args, enum: EnumType, **kwargs):  # type: ignore
    help = kwargs.pop('help', None)
    if help is not None:
        choices_str = enum_choices(enum).replace('%', '%%')
        help = help.replace('%(choices)s', choices_str)
    parser.add_argument(*args, metavar=enum_metavar(enum), type=enum_parser(enum), help=help, **kwargs)


class ArgumentParser(argparse.ArgumentParser):
    def add_enum_argument(self, *args, enum: Enum, **kwargs):  # type: ignore
        add_enum_argument(self, *args, enum, **kwargs)
