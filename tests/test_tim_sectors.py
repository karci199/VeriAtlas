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


def test_old_country_names_join_the_new_ones():
    from veriatlas.adapters.tim_countries import country_code

    assert country_code("ÇİN HALK CUMHURİYETİ") == country_code("ÇİN")
    assert country_code("BİRLEŞİK DEVLETLER") == country_code("ABD")
    assert country_code("DUBAİ") == country_code("BAE")
    assert country_code("CEBELİ TARIK") == country_code("CEBELİTARIK")
