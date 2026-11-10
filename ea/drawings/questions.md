# Clarification questions (pink stickies), full history

Nothing is ever deleted from this file. When a question is answered, the answer and date are added and the status changes; the question stays.
Ids: Q-CJ1-v0.1-nn are the original CJ1 v0.1 stickies (5 Nov 2026) that were lost from the Miro board when the v0.1 to v0.3 images were replaced. Later ids follow the numbering used on the drawings.

## CJ1 "PPC to Paying", original v0.1 stickies (5 Nov 2026)
| Id | Stage | Question | Status | Answer (who, when) |
|---|---|---|---|---|
| Q-CJ1-v0.1-01 | s1 Ad / lead gen | Which landing page per campaign (website, Slerp shop, Trifft download)? Is there a UTM convention? | OPEN | Michael 6 Nov: unknown, marketing to answer (now CJ1 pink 5) |
| Q-CJ1-v0.1-02 | s1 Ad / lead gen | Is any ad click ever joined to a sale (closed-loop attribution), or does attribution stop at the pixel? | OPEN | Marketing to answer (CJ1 pink 5) |
| Q-CJ1-v0.1-03 | s2 Discover | Which CMS runs the website, and who edits venue hours there vs in Google Business Profile? | ANSWERED | WordPress; Google Business Profile owned by marketing (Michael, 6 Nov) |
| Q-CJ1-v0.1-04 | s3 Order / book | Which table booking system is live (Kobas bookings, OpenTable, ResDiary, other)? Does it write into Kobas? | ANSWERED | Dojo Bookings, not written into Kobas (Michael, 6 Nov) |
| Q-CJ1-v0.1-05 | s3 Order / book | Slerp to Kobas: via Deliverect or direct? | ANSWERED | Via Deliverect, straight to the kitchen printer (Michael, 6 Nov) |
| Q-CJ1-v0.1-06 | s3 Order / book | QR order-at-table: which sites live, which acquirer inside the QR flow? | PARTLY | Kobas own module, all sites (Michael, 6 Nov). Acquirer: Worldpay, Stripe and Slerp all given; still open (CJ2 pink 1) |
| Q-CJ1-v0.1-07 | s3 Order / book | Uber Eats / Just Eat: live on any site? | ANSWERED | No. Deliverect carries Deliveroo and Slerp only (Michael, 6 Nov) |
| Q-CJ1-v0.1-08 | s4 Pay | Who is the card acquirer and terminal provider (Dojo, Zettle, Worldpay, other)? Integrated with the Kobas till or standalone? | PARTLY | Paymentsense / Dojo via Kobas Connect, standalone PDQ on some venues (Kobas extraction, 5 Nov). Dojo as acquirer of record on bank statements still to confirm |
| Q-CJ1-v0.1-09 | s4 Pay | Payment level 2: terminal to acquirer to settlement file to Xero bank feed. Who reconciles, where does the Slerp / Stripe payout show up? | OPEN | Taken into CJ3 "Sale to Bank to Books" (pinks 9, 10, 12, 16). Marketing reconciles Slerp and Deliveroo payouts (Michael, 6 Nov) |
| Q-CJ1-v0.1-10 | s5 Loyalty | Is Trifft integrated with the Kobas till (reward applied automatically) or is the discount keyed by hand? | ANSWERED | Auto-applied, lands in Kobas as an auto-applied discount (Michael, 6 Nov) |
| Q-CJ1-v0.1-11 | s5 Loyalty | Does a Trifft member link to a Kobas customer record, or are they two separate customers? | PARTLY | Extraction: meta_trifft_location_id per venue, Kobas customer holds loyalty cards and net_points. Not confirmed by the business |

## CJ1 consolidated list (v0.3, 5 to 6 Nov)
| # | Question | Status |
|---|---|---|
| 1 | Table booking system, writes to Kobas? | ANSWERED (Dojo, no) |
| 2 | Slerp to Kobas route | ANSWERED (Deliverect) |
| 3 | Trifft reward auto-applied or keyed | ANSWERED (auto) |
| 4 | Website CMS, owner of venue hours | ANSWERED (WordPress, marketing) |
| 5 | Landing page, UTM convention, closed-loop attribution | OPEN (marketing) |
| 6 | QR order-at-table sites and acquirer | PARTLY (all sites; acquirer = CJ2 pink 1) |
| 7 | Which Xero org per venue (6 seen), where payouts land, who reconciles | OPEN (CJ3 pinks 7, 12) |
| 8 | Tab / payment / receipt at record level | ANSWERED (in Kobas under Customers, extractable) |

## CJ2 "Order to Kitchen to Served"
| # | Question | Status |
|---|---|---|
| 1 | QR payment acquirer: Worldpay, Stripe or Slerp (three answers given) | OPEN |
| 5 | Void reason captured in Kobas? | OPEN |
| 6 | Station routing rules: Kobas item_category / till_page, or set on the printer? | OPEN |
| 7 | Allergens: which of the five copies (Kobas, Mapal, Slerp, Trifft, pay-at-table) is the master? | OPEN |
| 2, 3, 4, 8, 9, 10 | (see notes/cj2-draft.md) | ANSWERED 6 Nov |

## CJ3 "Sale to Bank to Books"
| # | Question | Status |
|---|---|---|
| 7 | Venue to Xero org map (6 orgs seen) | OPEN |
| 8 | Cash: who counts and banks it, how, cadence; where petty cash closes | OPEN |
| 9 | Dojo: settlement timing, gross or net of fees, fee invoice | OPEN |
| 10 | Stripe (Slerp): payout cadence, bank account, who posts it | OPEN |
| 11 | Deliveroo: weekly statement net of commission and VAT; self-billing invoice in Hubdoc? | OPEN |
| 12 | Bank accounts per legal entity or per venue; which account each acquirer pays into | OPEN |
| 13 | Kobas Xero importer: live on every venue? What it posts | OPEN |
| 14 | Tips and service charge: posting in Xero, tronc | OPEN |
| 15 | Refunds, voids, deposits, gift vouchers treatment | OPEN |
| 16 | Owner of the daily bank vs cash log reconciliation per venue | OPEN |

## Marcel's review comments (Miro)
| Date | Where | Comment | Response |
|---|---|---|---|
| 6 Nov 2026 | EA 5-layer view | Map the Kobas API GET / PUT REST endpoints in layer 2 to the corresponding service methods in layer 3 | Done in CJ1_2 v0.6, CJ2_2 v0.4, CJ3_2 v0.1 (Integration surfaces strip and endpoint to method arrows) |
| 7 Nov 2026 | CJ1 swimlane | Version in git: the first version had good questions, now lost | This folder. v0.1 questions restored above and as pink stickies in the Archive frame on the board |
