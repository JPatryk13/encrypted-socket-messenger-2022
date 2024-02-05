import unittest
from datetime import datetime, time, date
from src.message_handler import SortByDate
import random
from math import floor


class TestSortByDate(unittest.TestCase):
    def setUp(self) -> None:
        self.timestamp_key = "timestamp"
        self.datetime_dict_list = [
            {
                self.timestamp_key: datetime(
                    2019,
                    int(1 + floor(i / 28)),
                    1 + i % 28,
                    random.randint(1, 23),
                    random.randint(1, 59),
                    random.randint(1, 59),
                    random.randint(1, 999999),
                )
            } for i in range(0, 10, 280)
        ]

    def test_find_datetime_value_key_just_date(self) -> None:
        input_val = {"key1": "foo", "key2": 5, "key3": datetime.now().date()}
        expected = ["key3"]
        actual = SortByDate.find_datetime_value_key(input_val)[0]
        self.assertEqual(expected, actual)

    def test_find_datetime_value_key_just_time(self) -> None:
        input_val = {"key1": datetime.now().time(), "key2": "foo", "key3": 5}
        expected = ["key1"]
        actual = SortByDate.find_datetime_value_key(input_val)[0]
        self.assertEqual(expected, actual)

    def test_find_datetime_value_key_datetime(self) -> None:
        input_val = {"key1": "foo", "key2": datetime.now(), "key3": 5}
        expected = ["key2"]
        actual = SortByDate.find_datetime_value_key(input_val)[0]
        self.assertEqual(expected, actual)

    def test_find_datetime_value_key_no_datetime_value(self) -> None:
        input_val = {"key1": "foo", "key2": 5}
        expected = []
        actual = SortByDate.find_datetime_value_key(input_val)
        self.assertEqual(expected, actual)

    def test_sort_by_date_single_entry(self) -> None:
        datetime_key = "foo"
        datetime_val = datetime.now().time()
        input_val = [{datetime_key: datetime_val, "key2": "foo", "key3": 5}]

        expected = input_val
        actual = SortByDate.sort_by_date(input_val, datetime_key)

        self.assertEqual(expected, actual)

    def test_sort_by_date_multiple_entries_just_time(self) -> None:
        datetime_key = "foo"

        expected = [{datetime_key: time(1, 1, int(floor(i / 1000000)), i % 1000000)} for i in range(0, 3000000, 100000)]
        input_val = random.sample(expected, len(expected))  # randomise order of entries
        actual = SortByDate.sort_by_date(input_val, datetime_key)

        self.assertEqual(expected, actual)

    def test_sort_by_date_multiple_entries_just_date(self) -> None:
        datetime_key = "bar"

        expected = [{datetime_key: date(2019, int(1 + floor(i / 28)), 1 + i % 28)} for i in range(0, 280, 10)]
        input_val = random.sample(expected, len(expected))  # randomise order of entries
        actual = SortByDate.sort_by_date(input_val, datetime_key)

        self.assertEqual(expected, actual)

    def test_sort_by_date_multiple_entries_datetime(self) -> None:
        datetime_key = self.timestamp_key
        input_val = random.sample(self.datetime_dict_list, len(self.datetime_dict_list))

        expected = self.datetime_dict_list
        actual = SortByDate.sort_by_date(input_val, datetime_key)

        self.assertEqual(expected, actual)

    def test_sort_by_date_multiple_entries_sorted(self) -> None:
        datetime_key = self.timestamp_key

        expected = self.datetime_dict_list
        actual = SortByDate.sort_by_date(expected, datetime_key)

        self.assertEqual(expected, actual)

    def test_sort_by_date_multiple_entries_same_datetime(self) -> None:
        datetime_key = self.timestamp_key

        expected = [self.datetime_dict_list[0] for _ in range(30)]
        actual = SortByDate.sort_by_date(expected, datetime_key)

        self.assertEqual(expected, actual)

    def test_find_datetime_value_key_embedded_timestamp_field(self) -> None:
        _list = []
        for _dict in self.datetime_dict_list:
            _list.append({"foo": _dict})

        expected = [["foo", self.timestamp_key]]
        actual = SortByDate.find_datetime_value_key(_list[0])

        self.assertEqual(expected, actual)

    def test_sort_by_date_embedded_timestamp_field(self) -> None:
        _list = []
        for _dict in self.datetime_dict_list:
            _list.append({"foo": _dict})

        keys = ["foo", self.timestamp_key]

        expected = _list
        input_list = random.sample(_list, len(_list))
        actual = SortByDate.sort_by_date(input_list, *keys)

        self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
