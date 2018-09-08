from typing import List, Optional, Union, TypeVar, Generic, Tuple, Iterator, Iterable, ClassVar, Any
from math import ceil
import sys

try:
    from humanfriendly.terminal import ansi_wrap, terminal_supports_colors
    have_ansi = terminal_supports_colors()
except ImportError:
    have_ansi = False

__all__ = ['TablePrinter', 'TableData']

class BaseTableElement:
    _width: Optional[int]

    def __init__(self) -> None:
        self._width = None

    @property
    def width(self) -> int:
        if self._width is None:
            self._width = self._calculate_width()
        return self._width

    def _calculate_width(self) -> int:
        raise NotImplementedError

    def _trigger_recalculate_width(self) -> None:
        self._width = None

    def _trigger_redraw_header(self) -> None:
        raise NotImplementedError

class BaseChildElement(BaseTableElement):
    _width: Optional[int]

    def __init__(self, parent: 'BaseTableParent') -> None:
        super().__init__()
        self._parent = parent

    def _trigger_recalculate_width(self) -> None:
        super()._trigger_recalculate_width()
        self._parent._trigger_recalculate_width()

    def _trigger_redraw_header(self) -> None:
        self._parent._trigger_redraw_header()

T = TypeVar('T', bound=BaseChildElement)
class BaseTableParent(BaseTableElement, Generic[T]):
    _columns: List[T]

    def __init__(self):
        super().__init__()
        self._columns = []

    def __len__(self) -> int:
        return len(self._columns)

    def __getitem__(self, i: int) -> T:
        colcount = len(self)
        if colcount > i:
            return self._columns[i]
        if colcount < i:
            raise IndexError("Can't access items greater than 0..len")
        # create new one
        column = self._create_child()
        self._columns.append(column)
        self._trigger_recalculate_width()
        return column

    def __delitem__(self, i: int) -> None:
        del self._columns[i]
        self._trigger_recalculate_width()

    def __iter__(self) -> Iterator[T]:
        return iter(self._columns)

    def _create_child(self) -> T:
        raise NotImplementedError

class LabelledTableElement(BaseTableElement):
    def __init__(self) -> None:
        super().__init__()
        self._label = ""

    @property
    def label(self) -> str:
        return self._label

    @label.setter
    def label(self, value: str) -> None:
        if len(self._label) != len(value):
            self._trigger_recalculate_width()
        elif self._label != value:
            self._trigger_redraw_header()
        self._label = value

    @property
    def centered_label(self) -> str:
        return self.label.center(self.width)


class Value:
    NONE: ClassVar['Value']

    def __init__(self, value: Union[str, float, int], stale: bool) -> None:
        self.value = value
        self.stale = stale

    def _format_value(self, width: int) -> str:
        value = self.value
        if isinstance(value, float):
            return f"{value:#{width}.2f}"
        return f"{value:>{width}}"

    def format(self, width: int) -> str:
        value = self._format_value(width)
        if have_ansi:
            return ansi_wrap(value, color='white', bold=not self.stale)
        else:
            return value if not self.stale else f"({value})"

Value.NONE = Value('', stale=False)

class Column(BaseChildElement, LabelledTableElement):
    _value: Value

    def __init__(self, parent: BaseTableParent) -> None:
        super().__init__(parent)
        self.expected_width = 0
        self._label = ""
        self._value = Value.NONE
        self._max_encountered_width = 0

    @property
    def value(self) -> Value:
        return self._value

    @value.setter
    def value(self, value: Value) -> None:
        self._value = value
        value_len = len(self.value._format_value(self.width))
        if value_len > self._max_encountered_width:
            self._max_encountered_width = value_len
            self._trigger_recalculate_width()

    def pop_value(self) -> str:
        value = self._value.format(self.width)
        self._value = Value.NONE
        return value
        
    def _calculate_width(self) -> int:
        lenlabel = len(self.label)
        width = max(self.expected_width, self._max_encountered_width, lenlabel)
        #if lenlabel % 2 == 1 and width % 2 == 0:
        #    width += 1
        return width

class ColumnGroup(BaseChildElement, LabelledTableElement, BaseTableParent[Column]):
    def __init__(self, parent: BaseTableParent) -> None:
        super().__init__(parent)

    def _create_child(self) -> Column:
        return Column(self)

    def _calculate_width(self) -> int:
        separator_width = 1
        column_padding = 2 # left and right
        num_cols = len(self._columns)
        cols_width = (
            sum(c.width for c in self._columns) 
            + (num_cols-1) * (column_padding + separator_width) # outer padding does not count
        )
        header_width = len(self.label)
        width = cols_width
        if header_width > cols_width:
            extra_padding = int(ceil((header_width - cols_width) / num_cols))
            width = header_width + (extra_padding % num_cols)
            for column in self._columns:
                column._width = column.width + extra_padding
        return width

class TablePrinter(BaseTableParent[ColumnGroup]):
    def __init__(self, out=sys.stdout):
        super().__init__()
        self._out = out
        self._needs_redraw_header = True
        self._header = None

    def _create_child(self) -> ColumnGroup:
        return ColumnGroup(self)
        
    def _trigger_recalculate_width(self) -> None:
        super()._trigger_recalculate_width()
        self._trigger_redraw_header()

    def _trigger_redraw_header(self) -> None:
        self._needs_redraw_header = True

    def _calculate_width(self):
        return sum(group.width for group in self) + 1

    def _print_header(self) -> None:
        width = self.width # make sure width is calculated
        self._print('┏━' + '━┳━'.join('━' * group.width for group in self) + '━┓')
        self._print('┃ ' + ' ┃ '.join(group.centered_label for group in self) + ' ┃')
        self._print('┣━' + '━╋━'.join('━┯━'.join('━' * column.width for column in group) for group in self) + '━┫')
        self._print('┃ ' + ' ┃ '.join(' │ '.join(column.centered_label for column in group) for group in self) + ' ┃')
        self._print('┡━' + '━╇━'.join('━┿━'.join('━' * column.width for column in group) for group in self) + '━┩')

    def _print_values(self) -> None:
        self._print('│ ' + ' │ '.join(' ┊ '.join(column.pop_value() for column in group) for group in self) + ' │')
        
    def _print(self, s: str, **kwargs: Any) -> None:
        print(s, file=self._out, **kwargs)
        self._out.flush()

    def print_values(self, values: Tuple) -> None:
        for i, (group_label, group_values) in enumerate(values):
            group = self[i]
            group.label = group_label
            for j, (col_label, col_value) in enumerate(group_values):
                col = group[j]
                col.label = col_label
                col.value = col_value
        if self._needs_redraw_header:
            self._needs_redraw_header = False
            self._print_header()
        self._print_values()




if __name__ == '__main__':
    pass

