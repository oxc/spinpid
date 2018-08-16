from typing import Optional, Iterable, Union

def parse_smart_temperature(output: Union[str, Iterable[str]]) -> Optional[int]:
    if not isinstance(output, Iterable) or hasattr(output, 'splitlines'):
        output = output.splitlines()
    
    def fielded_lines():
        for line in output:
            if not line:
                continue
            fields = line.split()
            if len(fields) == 0:
                continue
            yield fields

    lines = fielded_lines()
    for fields in lines:
        if fields[0] == 'ID#':
            break
    for fields in lines:
        if fields[0] == '194':
            return int(fields[9])
    return None
