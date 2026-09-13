"""Vehicle labels: a name holding " Ve " must not split, an unknown code must not pass."""

from veriatlas.adapters.tuik_vehicles import read_label


def test_name_with_ve_inside_is_one_part():
    label = "1. (Kaydı Yapılan) ve 8. (Yol Ve İş Makinaları)"
    assert read_label(label, ("registration", "vehicle_type")) == {
        "registration": "registered",
        "vehicle_type": "construction_machinery",
    }


def test_unknown_code_is_rejected():
    assert read_label("7. (Hidrojen)", ("fuel",)) is None
    assert (
        read_label("99999. (Yok Marka) ve 1. (Otomobil)", ("brand", "vehicle_type"))
        is None
    )


def test_part_count_must_match_dims():
    assert read_label("1. (Otomobil)", ("brand", "vehicle_type")) is None
