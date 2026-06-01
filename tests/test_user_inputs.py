from user_inputs.years import parse_years


def test_parse_years_list():
    assert parse_years([2020, 2019]) == [2019, 2020]


def test_parse_years_range():
    assert parse_years("2019-2021") == [2019, 2020, 2021]


def test_parse_years_csv():
    assert parse_years("2020, 2022") == [2020, 2022]
