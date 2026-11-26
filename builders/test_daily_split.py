#!/usr/bin/env python3
"""Regression test for the FOH/BOH split reader in pull_daily_cashup.py.

Every row below is a REAL row of `Raw Data 2` (columns J..W, i.e. idx 9..22) that the
old reader got wrong, plus rows it always got right. Run before every daily build:

    python3 builders/test_daily_split.py        (exit 0 = pass, 1 = fail)

Added 26/11/2026 after M7 SJQ on Tue 24/11 was published FOH 54.7% / BOH 45.3% when the
sheet says 45.3% / 54.7% (a projected figure had been paired with an actual one).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pull_daily_cashup as PC

# (label, cells idx 9..22, expected FOH, expected BOH, expected status)
CASES = [
    # the 24/11 flip: BOH projected + FOH actual sat within 94p of total labour
    ("M7 24/11/2026 flip", "2,077.57|148.2|1,009.93|48.61%|1,067.64|51.39%|885.65|45.31%|1,068.89|54.69%|1,954.54||1,952.35|129.70", 885.65, 1068.89, "ok"),
    ("M20 07/11/2026 flip", "2100.00||147.84|1137.85||842.47||1178.08|50.86%|1127.56|48.68%|2305.64|2316.35|159.60", 1178.08, 1127.56, "ok"),
    ("M19 02/09/2026 flip", "577.50|968.35|69.50|508.85|52.55%|31.50|3.25%|429.14|45.76%|491.98|52.46%|921.12|937.80|60.40", 429.14, 491.98, "ok"),
    ("M11 13/07/2026 flip", "682.50|582.55|44.50|209.10|35.89%|373.45|64.11%|186.25|33.28%|365.69|65.34%|551.94|559.71|38.30", 186.25, 365.69, "ok"),
    # a projected figure taken as FOH actual
    ("M10 12/11/2026", "1054.64||75.53|447.43|42.42%|509.95|48.35%|449.96|40.32%|665.88|59.68%|1115.84|1113.44|78.20", 449.96, 665.88, "ok"),
    ("M3 19/09/2026", "1505.00|1299.91|100.5|573.50|44.12%|726.41|55.88%|574.80|42.00%|793.74|58.00%|1368.54|1367.81|92.80", 574.80, 793.74, "ok"),
    ("M7 03/09/2026", "1982.86|140.13|903.90|45.59%|1078.96|54.41%|905.46|44.67%|1121.71|55.33%|2027.17||2024.98|135.50", 905.46, 1121.71, "ok"),
    ("M11 20/08/2026", "682.50|783.87|59.00|368.25|46.98%|415.62|53.02%|320.47|40.96%|414.36|52.95%|734.83|782.49|53.20", 320.47, 414.36, "ok"),
    # projected total + projected hours taken as the pair
    ("M18 18/08/2026", "840.00|1058.30|79.50|382.95|36.19%|603.74|57.05%|420.96|36.98%|636.88|55.95%|1057.84|1138.23|77.60", 420.96, 636.88, "ok"),
    ("M13 01/06/2026", "1050.00|1063.89|94.00|479.14|45.04%|584.76|54.96%|483.33|41.76%|580.72|50.17%|1064.05|1157.39|79.90", 483.33, 580.72, "ok"),
    # the whole projected pair taken as actual: the actual pair overshoots total, so UNVERIFIED with the ACTUAL figures
    ("M13 22/09/2026", "892.50|881.98|78.75|456.19|51.72%|425.79|48.28%|881.71|55.77%|776.45|49.11%|1658.16|1580.96|107.40", 881.71, 776.45, "unverified"),
    ("M13 19/12/2025", "1785.00|1580.04|118.50|740.39|46.86%|839.66|53.14%|737.37|46.65%|869.94|55.03%|1607.31|1580.73|118.80", 737.37, 869.94, "unverified"),
    # a coincidence the projected guard must NOT fall for (BOH proj + FOH actual = Budget to 2p)
    ("M12 27/05/2026", "808.50|962.27|70.00|451.14|46.88%|358.61|37.27%|449.87|46.55%|516.57|53.45%|966.44|966.44|66.90", 449.87, 516.57, "ok"),
    # rows the old reader already had right: must not move
    ("M7 23/11/2026", "1,982.37|139.65|913.44|46.08%|1,068.93|53.92%|863.40|42.00%|1,192.42|58.00%|2,055.82||2,055.82|136.70", 863.40, 1192.42, "ok"),
    ("M7 25/11/2026", "1,953.24|138.7|898.81|46.02%|1,054.43|53.98%|843.81|44.10%|1,069.45|55.90%|1,913.26||1,913.26|129.00", 843.81, 1069.45, "ok"),
    ("M18 24/11/2026", "945.00|1297.24|85.00|494.00|38.08%|803.24|61.92%|542.04|43.53%|713.17|57.27%|1255.21|1245.22|83.30", 542.04, 713.17, "unverified"),
    ("M1 10/11/2026", "525.00|561.09|39.9|171.59|30.58%|389.50|69.42%|175.80|30.26%|405.26|69.74%|581.06|581.06|39.30", 175.80, 405.26, "ok"),
    ("M3 31/10/2026 unallocated", "1505.00|1359.10|103|632.69|46.55%|726.41|53.45%|584.39|45.08%|712.02|54.92%|1296.41|1401.20|97.60", 584.39, 712.02, "ok"),
]


def run():
    bad = 0
    for label, cells, foh, boh, status in CASES:
        row = [""] * 9 + cells.split("|") + [""] * 6
        total = PC.num(row[PC.IDX_LABOUR_TOTAL])
        got = PC.extract_split(row, total, "T", "test", [])
        ok = (got[0], got[2], got[4]) == (foh, boh, status)
        bad += 0 if ok else 1
        print(("PASS " if ok else "FAIL ") + label + ("" if ok else f"  got FOH {got[0]} BOH {got[2]} {got[4]}, want {foh} {boh} {status}"))
    print(f"{len(CASES) - bad}/{len(CASES)} passed")
    return bad


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
