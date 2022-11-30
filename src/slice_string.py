import re


def slice_string(
        _str: str,
        slice_lengths: list[int],
        *, start_at: int = 0,
        support_mixed_dtype: bool = False,
        force_str: bool = False) -> list[float | int | str]:
    """
    Split string based on given args and match the output to either int, float or str. Example:
        >>> _str = "foobarexample"
        >>> x, y = slice_string(_str, [3, 2], start_at=2)
        >>> print([x, y])
        ["oba", "re"]

        >>> _str = "0020150203122516684638"
        >>> timestamp = slice_string(_str, [4, 2, 2, 2, 2, 2, 6], start_at=2)
        >>> print(timestamp)
        [2015, 2, 3, 12, 25, 16, 684638]

    :param _str: string to be sliced
    :param slice_lengths: lengths of slies to be returned
    :param start_at: the index to start at (including the character present at it)
    :param support_mixed_dtype:
    :param force_str:
    :return: sliced string - each element converted to float, int, str
    """
    # throw an error if the IndexError may occur in the code below
    if len(_str) < start_at + sum(slice_lengths):
        raise IndexError(f"start_at and slice_lengths add up to {start_at + sum(slice_lengths)} while length of the "
                         f"string is {len(_str)}.")

    _type = str
    if force_str:
        support_mixed_dtype = False
    else:
        # if support_mixed_dtype=False set conversion to int / float / str - check if conversion possible in that order
        if not support_mixed_dtype:
            if _str.isdigit():
                _type = int
            elif all(list(map(lambda s: s.isdigit(), _str.split('.')))):
                _type = float

    slices = []

    # current_index will keep track of the progress through the string
    current_index = start_at

    # iterate through the slice_lengths list and slice the given string
    for slice_len in slice_lengths:
        # extract a slice of the string
        _slice = _str[current_index:current_index + slice_len]

        # update current_index
        current_index += slice_len

        # convert slice to the predefined type
        converted = _type(_slice)

        # convert the slice to float or int if possible and if support_mixed_dtype=True
        if support_mixed_dtype:
            if _slice.isdigit():
                converted = int(_slice)
            elif re.match(r'^-?\d+(?:\.\d+)$', _slice):
                converted = float(_slice)

        slices.append(converted)

    return slices