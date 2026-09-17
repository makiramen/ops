# Keyline Control, offline (17 Sep 2026)

The Keyline morning runs here, in GitHub Actions (`.github/workflows/keyline-daily.yml`), with no Mac,
no Chrome and no Claude session in the loop. It logs into Kobas as the keyline bot user, pulls the nine
stock positions and six weeks of orders and deliveries, builds the board, emails Sophie and O, and pushes
`keyline.html` plus the state files in this folder.

## Secrets the workflow needs (repo Settings > Secrets and variables > Actions)

| secret | value |
|---|---|
| `KOBAS_COMPANY_ID` | 3031 |
| `KOBAS_USERNAME` | the keyline bot user's Kobas username |
| `KOBAS_PASSWORD` | its password |
| `GMAIL_USER` | michael@makiramen.com (the address the 07:00 email sends from) |
| `GMAIL_APP_PASSWORD` | a Google app password for that account (needs 2-step verification on) |
| `OPS_DEPLOY_TOKEN` | already set (the fine-grained PAT the other pipes push with) |

The bot user needs Reports (stock current position) and Operations > Orders and Deliveries read access at
the nine venues. Never Michael's own login: the script signing in at 06:55 would end his Chrome session.

## The cycle (order is load-bearing)

```
kobas_pull.py                  Kobas -> pull.txt (stock) and part_orders.html (orders, deliveries)
build_data.py <version>        pull.txt -> part_data.html
build_asks.py prepare          part_asks.html = ask days UP TO YESTERDAY (never today)
cat 8 parts                    keyline-control.html
render.py                      verify, stamp redSites, write asks-<date>.json and mail.html
cat 8 parts again              stamped data into the page
build_asks.py commit <date>    remember today for tomorrow
mkmail.py / compact_mail.py / make_rl2.py     email body and the small PDF
SMTP send                      sophie@makiramen.com and srawut@makiramen.com, fixed, never anyone else
wrap, commit, push             ../keyline.html + the state files here
```

`keyline_cloud_run.py` does all of that. Flags: `--no-pull` (build from the files here), `--no-email`,
`--no-push`, `--report path`. Exit 30/31/32 = Kobas could not be pulled: the "estate blind" email goes
out and nothing is built. Exit 33 inside the pull = orders failed, the board still ships on the previous
orders file and says so in the run summary. Exit 40 = the page did not render clean, nothing ships.

## Two cron slots, one email

06:55 UK and a 07:40 UK retry. The guard step skips the retry when `pull-<today>.txt` is already on
main, so a delayed first slot never produces two emails. `workflow_dispatch` takes `no_email` (ship the
board, do not email) and `force` (run even if today shipped).

## The engine itself

`part_a` (CSS) `part_b` (items, PAR, routes, usage) `part_c` (Today, By site, order guide) `part_e` (order
compliance and closure) `part_d` (email, exceptions, boot). Edit these here; the Mac copy under
"Keyline Control/" is no longer what runs. The page version is read from `part_data.html` meta.version
(or `KEYLINE_VERSION` in the environment) and written back by `build_data.py`.
