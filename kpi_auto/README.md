# kpi_auto: KPI sheet automation (Kobas direct, no email skim)

Workflow: `.github/workflows/kpi-auto.yml` (manual dispatch). Output goes to the KPI Auto sheet
`14_rQMgMu7TaHagGkgHYe-7mNar_QWyy-3yUgRoW4H8Y`. Nothing is written to site KPI sheets unless `write_mode=apply`.

## What the site sheets hold today
`Script Data` in every site KPI sheet is a straight copy of the Kobas scheduled report **Daily Headline Revenue**
(emailed to Matt, skimmed into his sheet `14IWgUJUu6WUllP7AO0LjDGgoQqybUMJSh8uwQsLbo3Y`). Proved 23/10/2026: 408/408
Script Data cells, 28/09 to 21/10. The report ran ~08:00 UK until 22/10 and 04:00 UK from 23/10.

## Field map (Kobas direct, rebuilt in `kobas_daily.py` -> `Kobas_Daily` tab)
| Script Data | Kobas source | Rule |
|---|---|---|
| Sit in | Cash Log report `/data/reports/cash-log` eat-in + takeaway net | x1.2, round 2 (Nori has no split: net) |
| Delivery | Cash Log delivery net | x1.2 |
| Actual | eat-in + takeaway + delivery net | x1.2 |
| Tips | Service Charge + PDQ Tips + Other Tips + Cash Tips | |
| Declared Rev | Declared Payments - Tips | |
| Wet Sales | Cash Log wet sales (net) | |
| Hours work Cost / Hours Used | Labour Costs report (queue key `labour_costs_report`, export `/data/reports/labour-costs/{id}/export`) Hours Worked Cost (incl. employer NI) / Hours Worked | must be the morning-after report; hours 0 when no sales |
| Food Cost Actual | stock orders `/data/v2/stock/order` total, delivered_date = day, last modified before the morning cut-off | list per venue ordered by id (log_date offset paging skips rows) |
| Cost of Waste / Comp / Directors | Stock Usage report (queue key `stock_usage_report`, storage_format csv, export `/data/reports/stock-usage/{id}/export`) net cost by usage type | all waste logged by pull time |
| Potential Gross Revenue Lost | dropped (Michael, 23/10/2026) | |

## Why history cannot all match today
Kobas data changes after the morning report (late clock fixes, orders confirmed or edited late, waste logged late, tips
reclassified, recipe costs revalued). The sheet holds the morning value. A daily pull just after the Headline report
(~04:10 UK) freezes the same values; 22/10 pulled the same morning matched every field except 3 cells changed after 04:00.

## DAY (Input) fields typed by managers (LIVE from the 24/10/2026 04:10 run)
Michael's rulings 23/10/2026, one rule for every site: Covers = Kobas covers (Cash Log report); Drinks % / Sushi % / Sides % =
category gross (incl. VAT) over total gross (incl. VAT) from All Item Sales, every menu incl. delivery. Built in `kobas_daily.py`
(Kobas_Daily columns Covers, Drinks %, Sushi %, Sides %), planned and written by `writer.py` into the `DAY (Input)` tab of each
site sheet (headers matched by regex: customers|covers, ^drinks, ^sushi, ^sides). The scheduled run is `write_mode=apply` with
`apply_fields=Covers,Drinks %,Sushi %,Sides %`: blank or zero cells only, a figure a manager typed is never overwritten, a formula
never written, no rows appended. % is written as '12.34%' when the column is percent-formatted, plain otherwise. Script Data stays
plan-only. Dispatch with `plan_to_repo=1` to commit the compact plan (`kpi_auto/plan/day_plan_<from>_<to>.csv` + writer log).

## Sales forecast push to Kobas (`forecast_push.py`, 23/10/2026)
Daily in the 04:10 UTC run (schedule = apply; dispatch input `forecast` = plan / apply / skip). Rolling 28 days from today (UK).
- Source: site KPI sheet `DAY (Input)`, target = Sit In target (col C) + Delivery Gross target (col D). Sheets are filled to 31/12/2026 (M6 to 06/12).
- Kobas screen: Rotas > Sales Budgets (`/admin/budgets/`), one row per venue per week Mon..Sun.
  New week: CSV upload `POST /admin/budgets/index.php` (multipart `budgetfile`, `m=save`). Re-uploading an existing week is ignored by Kobas.
  Existing week: `PUT /admin/budgets/getupdatesbudget.php` (id, mon..sun), returns the saved row.
- Days before today and after the window keep the Kobas value. 25 Dec is never written (Michael): Kobas stores 0 for that blank day on a new week.
- Every in-window day is read back and verified; the plan/result is written to the `Forecast_Push` tab of KPI Auto.
- Proved by hand 23/10/2026 on M9 (venue 2) W/C 26/10: upload, PUT change and PUT back all landed.
