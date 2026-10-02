# Site Control Centre nightly pipeline (build 1, 02/10/2026)

## What runs
GitHub Actions `site-cc-nightly.yml` in makiramen/ops at 05:30 UK (nightly) and 09:30 UK (cash up). For every site in sites.json with "live": true it runs the pulls, builds the page and commits `site/<CODE>/index.html` (offline standalone page) plus `build_log.json`. Each pull is its own fault domain: a failed pull keeps the last good file and the page shows a Maki orange "Late data" bar naming the feed. A failed build writes nothing, so the last good page stays live.

## Built and verified (against the v22 data)
| Script | Feed files | Source | Verified |
|---|---|---|---|
| build.py | all | feed files only (no data in code) | v22 output byte identical |
| pipeline/pull_amcc.py | weekly.json, eff.json, effall.json, stand.json (eff) | AM CC data/M14_wc_*.json, all_sites_wc_*.json | all 21 weeks identical |
| pipeline/pull_cashup.py | daily.json, covers.json, delivery.json | Auto Cash Up, Raw Data 2 (Sheets API) | 10 saved exports, 0 differences |
| pipeline/pull_monalisa.py | ml_weekly.json, labour.json | Mona Lisa, Input Tabs (Sheets API) | all 21 weeks identical |
| pipeline/pull_broth.py | broth.json | ops builders/broth/live_matrix.txt (Mapal, broth-tab.yml) | logic from the seed; live file not in this folder |

## Not yet built (build 2)
Google reviews (google-reviews repo master JSON, keeps reviewReply), loyalty (Ramen Royalty sheet, DAILY VISITS tab), compliance (tracker now, Mapal compliance next), team (Onboarding Tracker), EOTM (Hanna's sheets), key lines (Keyline Control output in ops), meeting notes (AM: Gmail task; GM/HC: folder), Mapal hygiene, intangibles and food quality, claude.ai artifact republish, other sites (src.html still says M14 and Meadowhall in 23 places).

## One time setup (Michael)
1. Google Cloud: in project maki-reviews enable the Google Sheets API, create a service account (for example site-cc-reader), create a JSON key.
2. Share as Viewer with the service account email: Auto Cash Up (1T4TtCs-SkBjinToxG45oKksUiPPPIllo2Pqrqbaix6w) and Mona Lisa (1_yzry0OCWA9N6-I9mWxmAFwfBqMWwEzMN3kPpSp6HJw). Build 2 adds the Compliance Tracker, Onboarding Tracker, Hanna's EOTM sheets and Ramen Royalty.
3. makiramen/ops, Settings, Secrets and variables, Actions: new secret SITE_CC_SERVICE_ACCOUNT_JSON = the whole key file.
4. Copy into makiramen/ops: this folder's build.py, src.html, sites.json, pipeline/ into `site_cc/`; the feed JSON files into `site_cc/data/M14/`; `deploy/.github/workflows/site-cc-nightly.yml` into `.github/workflows/`.
5. Actions tab, Site Control Centre nightly, Run workflow. Check `site/M14/build_log.json`.

## Local test without Google
`python3 build.py --out /tmp/x` rebuilds from the files here. Each pull takes `--csv <export>` and `--check` (compare only, writes nothing).
