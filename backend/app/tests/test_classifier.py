from app.services.classifier import classify_asset, classify_event
from app.services.ons_whitelist import is_on, normalize_ticker


def test_normalize_ticker():
    assert normalize_ticker("MRCAD") == ("MRCA", "D")
    assert normalize_ticker("MR35D") == ("MR35", "D")
    assert normalize_ticker("YMCJC") == ("YMCJ", "C")
    assert normalize_ticker("AL30") == ("AL30", "")
    assert normalize_ticker("") == ("", "")
    # IOL "US$" suffix on CEDEAR dividend rows
    assert normalize_ticker("AAPL US$") == ("AAPL", "D")
    assert normalize_ticker("HMY US$") == ("HMY", "D")
    assert normalize_ticker("BPOC7 US$") == ("BPOC7", "D")
    assert normalize_ticker("SPY USD") == ("SPY", "D")
    assert normalize_ticker("KO U$S") == ("KO", "D")


def test_is_on_whitelist():
    assert is_on("MRCAD") is True
    assert is_on("MR35D") is True
    assert is_on("YMCJD") is True
    assert is_on("AL30") is False
    assert is_on("AAPL") is False


def test_classify_asset_on_via_whitelist():
    assert classify_asset(simbolo="MRCAD", tipo=None, descripcion=None) == "ON"
    assert classify_asset(simbolo="MR35D", tipo=None, descripcion=None) == "ON"
    assert classify_asset(simbolo="MR35", tipo=None, descripcion=None) == "ON"


def test_classify_asset_bono_soberano():
    assert classify_asset(simbolo="AL30", tipo=None, descripcion=None) == "Bono"
    assert classify_asset(simbolo="GD30", tipo=None, descripcion=None) == "Bono"


def test_classify_asset_cedear_from_descripcion():
    assert (
        classify_asset(simbolo="AAPL", tipo=None, descripcion="CEDEAR APPLE")
        == "CEDEAR"
    )


def test_classify_asset_from_tipo():
    assert classify_asset(simbolo="X", tipo="CEDEAR") == "CEDEAR"
    assert classify_asset(simbolo="X", tipo="TitulosPublicos") == "Bono"
    assert classify_asset(simbolo="X", tipo="ObligacionNegociable") == "ON"
    assert classify_asset(simbolo="X", tipo="Acciones") == "Acción"


def test_classify_asset_us_market_default_cedear():
    assert classify_asset(simbolo="TSLA", tipo=None, mercado="estados_unidos") == "CEDEAR"


def test_classify_event_compra_venta():
    assert classify_event(tipo="Compra", simbolo="GGAL")[0] == "COMPRA"
    assert classify_event(tipo="Venta", simbolo="GGAL")[0] == "VENTA"


def test_classify_event_renta_on_usd_mep():
    ev, cur = classify_event(
        tipo="Pago de dividendos",
        descripcion="Renta y amortización",
        simbolo="MRCAD",
        moneda="Dolar Estadounidense",
        asset_class="ON",
    )
    assert ev == "RENTA"
    assert cur == "USD_MEP"


def test_classify_event_amortizacion_on():
    ev, _ = classify_event(
        tipo="Amortización", simbolo="MR35D", moneda="USD", asset_class="ON"
    )
    assert ev == "AMORTIZACION"


def test_classify_event_dividendo_cedear_cable():
    ev, cur = classify_event(
        tipo="Pago de dividendos",
        descripcion="Dividendo en efectivo",
        simbolo="AAPLO",
        moneda="Dolar Cable",
        asset_class="CEDEAR",
    )
    assert ev == "DIVIDENDO"
    assert cur == "USD_CABLE"


def test_classify_event_compra_ars_default():
    _, cur = classify_event(tipo="Compra", simbolo="GGAL", moneda="Pesos")
    assert cur == "ARS"


def test_classify_event_unknown_falls_back():
    ev, _ = classify_event(tipo="Algo raro", simbolo="X", moneda="ARS")
    assert ev == "OTRO"


def test_classify_event_dividendo_aapl_us_dollar():
    ev, cur = classify_event(
        tipo="Pago de dividendos",
        simbolo="AAPL US$",
        moneda=None,
        asset_class="CEDEAR",
    )
    assert ev == "DIVIDENDO"
    assert cur == "USD_MEP"


def test_classify_event_dividendo_hmy_us_dollar():
    _, cur = classify_event(tipo="Pago de dividendos", simbolo="HMY US$", moneda=None)
    assert cur == "USD_MEP"


def test_classify_event_dividendo_bpoc7_us_dollar():
    _, cur = classify_event(tipo="Pago de dividendos", simbolo="BPOC7 US$", moneda=None)
    assert cur == "USD_MEP"


def test_classify_event_compra_on_suffix_o_is_ars():
    # YM34O is an Argentine ON (YPF), suffix O is part of the ticker, not USD_CABLE marker
    ev, cur = classify_event(
        tipo="Compra",
        simbolo="YM34O",
        moneda="Pesos",
        asset_class="ON",
    )
    assert ev == "COMPRA"
    assert cur == "ARS"
