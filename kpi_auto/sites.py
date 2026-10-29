"""Site code -> KPI sheet spreadsheet id, shared by kpi_sheets.py (reader) and writer.py.
TRIAL (Michael, 29/10/2026): env SITE_SHEETS, a JSON map {"M3": "<sheet id>"}, REPLACES the whole map for that run, so a
trial run touches only the sheets named there (the copies in Matt's "Maki Claude" Drive folder), never a live site sheet."""
import os as _os, json as _json
SITES = {'M1': '1Wmb8_M9voUrC5nQvApf827Md46-oNlKfIziL7r4OvDw', 'M3': '1gkDCfjcrZi6Y61DYDQFWYGQcZ2Xptq7f7zT4A8vuWmc',
  'IKI2': '1wdUqS5ioV_POenDm2HY5nABHwBJlcxcWZiN3GSj5H_8', 'M6': '12zEnyvpZMTfAoqc38v5LUUEMBVKRdQPD7WaMZqOV8LM',
  'M7': '1ONnfA4wDzBxKF8k6699KU4WJ6Sy6BB3TE3yTYAvAgC4', 'M8': '1Q66O_Jbvym4Y4eHOTE-sLqGycBPgScv8vNSSn5i0Hc0',
  'M9': '1_qiuShHfi3oZ86CQQsiMZ5SlTHZOKIT1zdeRnUXNCaU', 'M10': '1PoMS4aEtq7AeIGu9e1d8J3MtXYcr13LljdRRUrMJYYg',
  'M11': '11VucIruJfIGM6DBbCwiXdVI2Bwgkh9Y7YaU9nQz4N6U', 'M12': '1IX4WVi-nZwx2ZLZyBAUYZBntanqdVpmGhVVDnVHxq3U',
  'M13': '1irmajiUeVu38J0GF14ZfllXokzwFMFRv8nd0Z-PyQsQ', 'M14': '1dw8FBc4Sbc5LKxJYFMasVEToJeY7I2uG2dc1DqKdlIo',
  'M15': '1xdU-wJW-7810WBptfyIYTGQDXvqEfT8lygHI4cXHdiI', 'M16': '1tKA401p9updPr5TyktK3Ym9Ebu8ebsjVbKMfF6VJoc0',
  'M17': '1Uo7cCAN12xM5BOLNfvwHI32Jx29Hp0UI-R7Iu_OJrSM', 'M18': '1U86lqCrgLY3s3vCm7W3iWPTDva-dXtGTDJualfbTIWE',
  'M19': '138Ss43VU-gbFxbIuMDhZ9Ymv1RVhAI9vDRcMrUNNiC4', 'M20': '17oa6qYz4jrwRpss0W7GWkIKvwuS3aa3Nw2T4lzCx0Ts',
  'M21': '1GJ2gTaxuANXJzNGBFQ0VZAMreTgogmWsaDrZpfye9T4', 'NORI': '1clXlYC-_W-8C6TqmCfpSuvJ-obXbrq3NmzHupL069II'}
_override = _os.environ.get('SITE_SHEETS', '').strip()
if _override:
    SITES = {k.strip().upper(): v.strip() for k, v in _json.loads(_override).items()}
    print('[sites] TRIAL override: only', ', '.join(f'{k} -> {v}' for k, v in SITES.items()), flush=True)
