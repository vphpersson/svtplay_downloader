from re import compile as re_compile, escape as re_escape
from typing import Dict, Any, Pattern


def expand_var(
    string: str,
    expand_map: Dict[str, Any],
    var_char: str = '%',
    exception_on_unexpanded: bool = False
) -> str:
    """
    Expand the variables in a string given a map.

    If an encountered variable name is not in provided map, the function can either ignore it, leaving
    the variable reference in-place, or raise an exception.

    Each encountered variable name is transformed to lowercase prior to the lookup in `expand_map`, thus all lookup
    keys (variable names) in `expand_map` should lowercase.

    :param string: The string to be expanded.
    :param expand_map: A name-to-value map of variable names and their corresponding values.
    :param exception_on_unexpanded: Raise an exception if an variable name in the string is not in the map.
    :return: The variable-expanded string.
    """

    var_char: str = re_escape(var_char)
    var_pattern: Pattern = re_compile(f'{var_char}(?P<variable_name>[^%]+){var_char}')

    search_start_offset = 0
    while match := var_pattern.search(string=string, pos=search_start_offset):
        var_pos_start, var_pos_end = match.span(0)

        variable_name: str = match.groupdict()['variable_name'].lower()
        if variable_name in expand_map:
            expanded_head: str = string[:var_pos_start] + str(expand_map[variable_name])
            string: str = expanded_head + string[var_pos_end:]
            search_start_offset: int = len(expanded_head)
        elif exception_on_unexpanded:
            raise KeyError(f'The variable name {variable_name} is not in the expand map.')
        else:
            search_start_offset: int = var_pos_end

    return string