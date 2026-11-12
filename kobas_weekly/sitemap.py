"""Site code -> Kobas venue id. Codes match the AM Control Centre data files (MakiNori, not NORI; MAF3 = Maki O2 Arena franchise).
Source: reference_kobas_item_sales_export venue map (10/09/2026) + kpi_auto. Kobas venue labels are never guessed: a venue
that is not here is listed under 'unmapped' in the output, never folded into a site."""
V = {'M1': 3, 'M3': 5, 'M6': 43, 'M7': 9, 'M8': 47, 'M9': 2, 'M10': 13, 'M11': 24, 'M12': 27, 'M13': 28, 'M14': 37,
     'M15': 41, 'M16': 42, 'M17': 49, 'M18': 51, 'M19': 58, 'M20': 60, 'M21': 61, 'MakiNori': 57, 'IKI2': 7, 'MAF3': 52,
     'MAF1': 18, 'MAF2': 21, 'MAF4': 63}   # 12/11/2026: franchises West End, Manchester NQ, Braehead (Kobas venue ids read 10/09/2026)
VID2S = {v: k for k, v in V.items()}
FRANCHISE = {'MAF1', 'MAF2', 'MAF3', 'MAF4'}
WET_CATS = ('ALCOHOLIC DRINKS', 'SOFT DRINKS')          # stock categories counted as wet (drinks)
CTRL_RX = r'CONTROLLABLE|PACKAGING|CONSUMABLE'         # stock categories counted as controllables (neither food nor wet)
