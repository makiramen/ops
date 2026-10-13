# EC Daily Spend Ledger inbox

Drop zone for parsed Head Chef Daily Report rows. The "Ec daily spend skim" scheduled task (cloud only, no Mac,
no Chrome) parses yesterday's Mapal emails and commits one JSON file here:

    data/ec_ledger_inbox/<YYYY-MM-DD>_<HHMM>Z.json   {"mode":"upsert","rows":[[date,site_code,daily_total,wtd_actual,wtd_left,hc_filed,suppliers_json,source,notes], ...]}

ec-ledger-post.yml wakes on that push, POSTs the payload to the EC Daily Spend Ledger appender (Apps Script web app,
upsert mode, idempotent), moves the file to applied/ with the response, and dispatches budget-burn-snapshot.yml.
