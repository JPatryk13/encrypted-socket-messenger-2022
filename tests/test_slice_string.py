import unittest
from src.slice_string import slice_string


class TestSliceString(unittest.TestCase):
    def test_slice_string_just_letters(self) -> None:
        _str = "foobarexample"
        expected = ["oba", "re"]
        actual = slice_string(_str, [3, 2], start_at=2)
        self.assertEqual(expected, actual)

    def test_slice_string_just_letters_start_at(self) -> None:
        _str = "foobarexample"
        expected = ["foo", "bar", "example"]
        actual = slice_string(_str, [3, 3, 7])
        self.assertEqual(expected, actual)

    def test_slice_string_index_error(self) -> None:
        _str = "foobarexample"
        self.assertRaises(IndexError, slice_string, _str, [3, 3, 7], start_at=5)
        with self.assertRaises(IndexError) as context:
            slice_string(_str, [3, 3, 7], start_at=5)
            self.assertTrue(
                "start_at and slice_lengths add up to 18 while length of the string is 13." in str(context.exception)
            )

    def test_slice_string_just_ints(self) -> None:
        _str = "0020150203122516684638"
        expected = [2015, 2, 3, 12, 25, 16, 684638]
        actual = slice_string(_str, [4, 2, 2, 2, 2, 2, 6], start_at=2)
        self.assertEqual(expected, actual)

    def test_slice_string_just_floats(self) -> None:
        _str = "2.346.2"
        expected = [2.34, 6.2]
        actual = slice_string(_str, [4, 3])
        self.assertEqual(expected, actual)

    def test_slice_string_int_and_str_support_mixed_dtype_false(self) -> None:
        _str = "245abcs"
        expected = ["245", "abcs"]
        actual = slice_string(_str, [3, 4])
        self.assertEqual(expected, actual)

    def test_slice_string_int_and_str_support_mixed_dtype_true(self) -> None:
        _str = "245abcs"
        expected = [245, "abcs"]
        actual = slice_string(_str, [3, 4], support_mixed_dtype=True)
        self.assertEqual(expected, actual)

    def test_slice_string_to_float_ipv4_format_split_between_digits(self) -> None:
        _str = "127.234.124.34"
        expected = [127.2, 34.12, 4.34]
        actual = slice_string(_str, [5, 5, 4])
        self.assertEqual(expected, actual)

    def test_slice_string_to_float_ipv4_format_split_before_comma(self) -> None:
        _str = "127.234.124.34"
        expected = [0.234, 0.124, 0.34]
        actual = slice_string(_str, [4, 4, 3], start_at=3)
        self.assertEqual(expected, actual)

    def test_slice_string_to_float_ipv4_format_split_after_comma(self) -> None:
        _str = "127.234.124.34"
        expected = [127.0, 234.0, 124.0]
        actual = slice_string(_str, [4, 4, 4])
        self.assertEqual(expected, actual)

    def test_slice_string_just_ints_force_str_true(self) -> None:
        _str = "0020150203122516684638"
        expected = ["00", "2015", "02", "03", "12", "25", "16", "684638"]
        actual = slice_string(_str, [2, 4, 2, 2, 2, 2, 2, 6], force_str=True)
        self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()