"""SGK national work accident tables: the silent paths."""

from veriatlas.adapters.sgk_national import category, column, drop_parents

HEAD = "title > title en > "


def test_days_block_under_same_title_is_not_counted_as_people():
    header = HEAD + "Geçici İş Göremezlik Süresi (gün) Days of Temporary Incapacity > İş Kazası > Erkek > 2"
    assert column(header) is None


def test_deaths_only_title_turns_plain_headers_into_deaths():
    header = HEAD + "İş Kazası(1) Work Accident > Erkek Male"
    assert column(header, deaths_only=True) == ("accident_death", "male", "all")


def test_total_columns_are_dropped_and_sex_totals_kept_for_checking():
    days = HEAD + "İş göremezlik sürelerine (gün) göre > "
    assert column(days + "Toplam Total > Toplam Total") is None
    assert column(days + "Toplam Total > Erkek Male") == ("accident", "male", "total")


def test_group_rows_are_removed_when_members_are_printed():
    rows = [("010", "a"), ("011", "a"), ("012", "a"), ("M65", "d"), ("M65.04", "d")]
    assert [r[0] for r in drop_parents(rows)] == ["011", "012", "M65.04"]


def test_workplace_size_ignores_the_repeated_band_code():
    assert category("1", "1-3 Çalışan - employees", "workplace_size", {}) == "1-3"
    assert category("5", "1000 + Çalışan - employees", "workplace_size", {}) == "1000+"


def test_occupation_major_group_needs_number_and_name():
    state = {}
    labels = ["0-Silahlı kuvvetler", "1-Subaylar", "11-Subaylar | 110-Subaylar", "1-Yöneticiler"]
    got = [category("", label, "occupation", state) for label in labels]
    # `1-Subaylar` sits under 0 and is not the managers' major group.
    assert got == ["0", None, None, "1"]
