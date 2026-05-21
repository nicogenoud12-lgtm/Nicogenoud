"""Whitelist of common Argentine Obligaciones Negociables (ONs).

Tickers come in multiple variants: base (ARS) + suffix D (MEP) + suffix C (CCL) +
sometimes suffix O (USD cable / hard dollar). We strip the trailing letter to
match the base ticker. The list is intentionally conservative — anything not
matched here falls back to other heuristics in classifier.py.
"""

# Base tickers (without ARS/MEP/CCL suffix). Includes well-known issuers:
# YPF (YMC*), Pampa Energía (MGC*), Telecom (TLC*, RCC*), Transportadora Gas Sur (CSO),
# Pan American Energy (PNX*), Vista Energy (VIS*), IRSA (IRC*), Cresud (CSD*),
# Aluar (ALU*), Galicia (GA38*), Mastellone (MRC*, MR35, MR36, MR37 — Marfrig family is
# different; this list focuses on Argentine corporates the user mentioned).
ON_BASE_TICKERS: set[str] = {
    # Mastellone Hnos
    "MRCA", "MR35", "MR36", "MR37", "MR38",
    # YPF — lettered series (YMCJ, YMCI, etc.)
    "YMCJ", "YMCI", "YMCH", "YMCK", "YMCM", "YMCN", "YMCO", "YMCP", "YMCQ",
    "YCAB", "YCAD", "YCA6",
    # YPF — numbered series (YM30–YM42): suffix D=MEP, C=CCL, O/none=ARS
    "YM30", "YM31", "YM32", "YM33", "YM34", "YM35", "YM36",
    "YM37", "YM38", "YM39", "YM40", "YM41", "YM42",
    # Pampa Energía
    "MGC1", "MGC9", "MGC3", "MGCC", "MGCJ", "MGCK", "MGCL", "MGCM", "MGCN",
    "MGCH", "MGCO", "MGCP",
    # IRSA / Cresud
    "IRCE", "IRCF", "IRCH", "IRCJ", "IRCK", "IRCL",
    "CSDO", "CSDR", "CSDS",
    # Telecom
    "TLC1", "TLC2", "TLC5", "TLC8",
    # Transportadora Gas del Sur
    "CSO1", "CSO5", "CSO9", "TSC1", "TSC5",
    # Pan American Energy
    "PNXJ", "PNXK", "PNXL", "PNXM", "PNXO",
    # Vista Energy
    "VSC1", "VSC5", "VSC9", "VSCT",
    # Aluar
    "ALUA",
    # Galicia
    "GA38",
    # Banco Hipotecario
    "BHI1",
    # PAE / Petrolera Argentina
    "PAE1", "PAE5",
    # Genneia / renewables
    "GNCXO", "GNCJ", "GNCK",
    # Loma Negra
    "LOMC",
    # Albanesi
    "ALCO", "ALCJ",
    # Capex
    "CP17",
    # Tecpetrol
    "TECG", "TECO",
    # Edenor
    "DNC1", "DNC3", "DNC5",
    # Generación Mediterránea
    "GMCJ", "GMCH", "GMCO",
    # Pampa CB
    "RCCJ", "RCCK",
    # Parex / etc reserved slots
    "PARA",
    # OceanTech / OTS series (ON USD)
    "OTS6", "OTS60",
}


def normalize_ticker(simbolo: str) -> tuple[str, str]:
    """Return (base, suffix).

    Suffix is one of: '', 'D' (MEP), 'C' (CCL), 'O' (USD cable / dolar billete).
    Examples:
        MRCAD      -> ('MRCA', 'D')
        MR35D      -> ('MR35', 'D')
        YMCJD      -> ('YMCJ', 'D')
        YMCJC      -> ('YMCJ', 'C')
        MRCA       -> ('MRCA', '')
        AAPL US$   -> ('AAPL', 'D')   # IOL CEDEAR dividend USD marker
        HMY US$    -> ('HMY',  'D')
    """
    if not simbolo:
        return ("", "")
    s = simbolo.upper().strip()
    # IOL uses " US$" / " USD" / " U$S" suffix on CEDEAR/dividend rows to signal USD
    for marker in (" US$", " USD", " U$S"):
        if s.endswith(marker):
            return (s[: -len(marker)].strip(), "D")
    if len(s) >= 2 and s[-1] in {"D", "C", "O"}:
        base = s[:-1]
        return (base, s[-1])
    return (s, "")


def is_on(simbolo: str) -> bool:
    base, _ = normalize_ticker(simbolo)
    return base in ON_BASE_TICKERS
