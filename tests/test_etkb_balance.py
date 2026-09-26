import pytest

from veriatlas.adapters.etkb_balance import product_columns


def test_subtotal_dropped_when_parts_printed():
    header = ["", "Linyit", "Petrol Ürünleri2", "Motorin", "Benzin", "TOPLAM"]
    assert product_columns(header) == {1: "coal", 3: "oil", 4: "oil", 5: "total"}


def test_unknown_column_rejected():
    with pytest.raises(ValueError, match="tanınmayan"):
        product_columns(["", "Linyit", "Hidrojen", "TOPLAM"])
