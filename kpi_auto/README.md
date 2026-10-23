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
| Potential Gross Revenue Lost | not rebuilt yet | needs EPoS item list prices |

## Why history cannot all match today
Kobas data changes after the morning report (late clock fixes, orders confirmed or edited late, waste logged late, tips
reclassified, recipe costs revalued). The sheet holds the morning value. A daily pull just after the Headline report
(~04:10 UK) freezes the same values; 22/10 pulled the same morning matched every field except 3 cells changed after 04:00.

## DAY (Input) fields typed by managers
Covers, drinks %, sushi %, sides % follow no single Kobas rule across sites (see KPI_Oct_Reconciliation, Manager-typed tab).
Need a ruling before automating.
