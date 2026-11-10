# Changelog

## 2026-11-10 (evening): CJ1 2 drill-down of s2, s3, s4
- Marcel, call of 10 Nov: revise s2, s3, s4 so they map to Kobas API entry points instead of repeating text; target is our own booking and ordering shop on the Kobas APIs, sitting between Kobas and Trifft (gradual migration).
- New drawings, v0.1: cj1/CJ1_2_s2_discover, cj1/CJ1_2_s3_order_book, cj1/CJ1_2_s4_pay. One column per derived story (level 2), five lanes, every layer 2 row a real entry point tagged by source: Kobas API v3, Kobas API v3 (path to confirm), no Kobas API, Trifft, Deliverect, Stripe, Maki Shop (to build).
- New component «Co27» Maki Shop (custom booking and ordering web app, to build).
- Finding: Kobas API v3 has no order, tab or payment write. Bookings and customers can be written (reservation, customer). The order write needs Deliverect Channel API or a Kobas partner push (as Preoday). Pinks 17 to 25 in questions.md.
- Source: source/cj1-drilldown.mjs (node, writes the three SVGs). CJ1 2 v0.6 stays as the overview.

## 2026-11-10
- Folder created in git after Marcel's review comment (7 Nov). All existing versions committed, v0.1 questions restored (questions.md).
- Board: CJ1 2 replaced by v0.6, CJ2 2 by v0.4, CJ3 set v0.1 added; older versions moved to an "Archive" frame with the v0.1 pink stickies.

## 2026-11-06
- CJ1_2 v0.6, CJ2_2 v0.4, CJ3_2 v0.1: Integration surfaces strip at the bottom of the System lane; Kobas API v3 endpoints (layer 2) mapped to layer 3 service contract methods (Marcel, 6 Nov). EPoS operations with no API marked "no API".
- CJ3 "Sale to Bank to Books" v0.1, full set (11 drawings).
- CJ1 v0.4 / CJ2 v0.2 posted to the board as SVG in named frames.
- CJ1 v0.4: every order lands in Kobas (QR, iPad, till natively; Slerp and Deliveroo via Deliverect); Michael's 6 Nov answers folded in.
- CJ2 v0.2: Order to Kitchen to Served, level 2 on the ordering points.
- CJ1 v0.3: correction, Kobas is the single order and payment hub (PNG kept: cj1/*/v0.3.png).

## 2026-11-05
- CJ1 v0.1: first draft, 11 pink stickies (v0.1 rendering not kept; its questions are in questions.md).
- Kobas extraction (ea/kobas/out).
