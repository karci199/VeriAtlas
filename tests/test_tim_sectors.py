"""TİM sector names: a renamed or new sector must stop the load, not vanish."""

import pytest

from veriatlas.adapters.tim_sectors import sector_code


def test_renamed_sectors_share_a_code():
    assert sector_code("Taşıt Araçları ve Yan Sanayi") == sector_code(
        "Otomotiv Endüstrisi"
    )
    assert sector_code("Elektrik - Elektronik") == sector_code("Elektrik ve Elektronik")
    assert sector_code("Mobilya,Kağıt ve Orman Ürünleri") == sector_code(
        "Ağaç Mamülleri ve Orman Ürünleri"
    )


def test_unknown_sector_is_refused():
    with pytest.raises(ValueError, match="tanınmayan sektör"):
        sector_code("Savunma ve Havacılık Sanayii")
