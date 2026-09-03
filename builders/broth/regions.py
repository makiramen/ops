# GetCompliant legal name -> (site code, display, region key)
# Built from the canonical site list. Legal names in Mapal are NOT the M-codes.
REGIONS = {
    "scotland": {"label": "Scotland & Newcastle", "dec": "Penny",  "am": "Ka Ho",   "order": 1},
    "midlands": {"label": "North England & Midlands", "dec": "Artur Mroczkowski", "am": "Inka Cheung", "order": 2},
    "south":    {"label": "South England", "dec": 'Srawut "O" Chairipu', "am": "Lincoln / Ziang", "order": 3},
    "franchise":{"label": "Franchise", "dec": "n/a", "am": "Matthew Jenner (BDM)", "order": 4},
    "unmapped": {"label": "Unmapped", "dec": "?", "am": "?", "order": 9},
}
SITES = {
    "M1TOO Ltd":              ("M1",   "Edinburgh Nicolson St", "scotland"),
    "Fountain Good Food Ltd": ("M3",   "Fountainbridge",        "scotland"),
    "Maki Bath St":           ("M6",   "Bath St, Glasgow",      "scotland"),
    "Maki SJQ Ltd":           ("M7",   "St James Quarter",      "scotland"),
    "Renfield Good Food Ltd": ("M8",   "Renfield St, Glasgow",  "scotland"),
    "Maki Newcastle Ltd":     ("M12",  "Newcastle Eldon Sq",    "scotland"),
    "Maki Aberdeen Ltd":      ("M13",  "Aberdeen",              "scotland"),
    "Maki METRO":             ("M15",  "Metrocentre",           "scotland"),
    "Maki Manchester LTD":    ("M9",   "Manchester",            "midlands"),
    "Maki Leeds Ltd":         ("M10",  "Leeds",                 "midlands"),
    "Maki Leicester Ltd":     ("M11",  "Leicester",             "midlands"),
    "Maki Meadowhall":        ("M14",  "Meadowhall",            "midlands"),
    "Maki Nottingham Ltd":    ("M16",  "Nottingham",            "midlands"),
    # Birmingham sits under South England. Confirmed by Michael 27 Aug 26
    # (geography says Midlands, the org does not: its Head Chef reporting ran
    # through the South DEC from opening).
    "Maki Birmingham Ltd":    ("M21",  "Birmingham",            "south"),
    "Maki Lakeside":          ("M17",  "Lakeside",              "south"),
    "Maki Soho":              ("M18",  "Soho",                  "south"),
    "Maki Shoreditch":        ("M19",  "Shoreditch",            "south"),
    "Maki Southampton":       ("M20",  "Southampton",           "south"),
    "Maki O2 Arena":          ("MAF3", "O2 London",             "franchise"),
}
UNCONFIRMED = {}

def resolve(legal_name):
    if legal_name in SITES:
        c, d, r = SITES[legal_name]
        return {"code": c, "site": d, "region": r,
                "unconfirmed": UNCONFIRMED.get(legal_name)}
    return {"code": None, "site": legal_name, "region": "unmapped", "unconfirmed": None}
