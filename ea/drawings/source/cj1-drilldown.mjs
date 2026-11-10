// CJ1 2 EA 5-layer view, level 2 drill-down of s2, s3, s4 (Marcel, 10 Nov 2026).
// One drawing per stage, one column per derived story, five lanes.
// Layer 2 rows are real API entry points, each tagged with its source and status.
// Run: node cj1-drilldown.mjs <outDir>   (writes three SVGs, styles inlined for Miro)
import fs from "node:fs";
import path from "node:path";

const VERSION = "v0.1";
const DATE = "10 Nov 2026";

// status of a layer 2 entry point
const ST = {
  api:   { label: "KOBAS API v3",            fill: "#d9f0d5", stroke: "#2f7d2b", text: "#163a14" },
  sub:   { label: "KOBAS API v3 · confirm path", fill: "#fff1c9", stroke: "#b58a00", text: "#4a3d00" },
  none:  { label: "NO KOBAS API",            fill: "#f8d3d3", stroke: "#b53030", text: "#5a1010" },
  trifft:{ label: "TRIFFT API",              fill: "#dfe6fb", stroke: "#3b56b5", text: "#152a66" },
  dlv:   { label: "DELIVERECT API",          fill: "#e3dcf5", stroke: "#6a48b5", text: "#2a1560" },
  stripe:{ label: "STRIPE API",              fill: "#dfe6fb", stroke: "#3b56b5", text: "#152a66" },
  slerp: { label: "SLERP WEBHOOK",           fill: "#dfe6fb", stroke: "#3b56b5", text: "#152a66" },
  ext:   { label: "OTHER VENDOR",            fill: "#dfe6fb", stroke: "#3b56b5", text: "#152a66" },
  build: { label: "MAKI SHOP · to build",    fill: "#ffe2c2", stroke: "#d97a16", text: "#5a3000" },
};

const TARGET = "Target (Marcel, 10 Nov): guest phone → «Co27» Maki Shop, our own booking and ordering web app (to build) → Kobas API v3 for reads and for reservation and customer writes · Deliverect Channel API for the order write (to verify) · Trifft API for member, coupons and points · Stripe for payment. Kobas stays the till and the system of record. The shop replaces the Kobas CIC front end and the Dojo booking widget: first step of a gradual migration.";

const DRAWINGS = [
{
  file: "CJ1_2_s2_discover",
  title: "CJ1 2.s2 Discover · EA 5-layer drill-down (level 2) · " + VERSION + " · " + DATE,
  stage: "s2 Discover",
  groups: [
    { id: "CJ1.s2.u1", name: "Finds venue, menu, hours", cols: 4 },
    { id: "CJ1.s2.u2", name: "Is recognised, sees own rewards (NEW: the shop sits between Kobas and Trifft)", cols: 2 },
  ],
  cols: [
    { id: "CJ1.s2.u1.1", story: "Scans the table QR, lands in the shop on the right venue and table",
      ux: ["NEW Maki Shop landing: venue and table preselected", "today: Kobas CIC To Table page"],
      se: "Se03 Venue Information", ops: ["resolveEntry(QrUrl): Venue, Table"],
      comps: ["Co27 Maki Shop (to build)", "Co7 Kobas"],
      today: "Today the QR holds a Kobas CIC URL per table (Kobas Cloud, Online Ordering, Tables tab). Deleting a table kills its QR.",
      eps: [
        { st: "api", m: "GET", p: "/venue/:id", n: "venue profile for the venue id carried in the QR" },
        { st: "none", p: "table list, table id per venue", n: "not in the API v3 catalogue. Tables live in Kobas Cloud only" },
        { st: "dlv", m: "GET", p: "Channel API: Get POS tables", n: "tables and floors of a POS location: alternative source" },
      ],
      ents: [["kobas.venue (97 fields)", "id, name, menu_id, epos_type, meta_deliverect_location_id, meta_trifft_location_id"],
             ["kobas.venue_online_ordering (45)", "eat_in_available, eat_in_automatically_approve, eat_in_estimation_minutes"],
             ["kobas table (CIC)", "name, area, customer facing. Not extracted yet"]],
      pinks: ["18 Table ids per venue: is there a Kobas endpoint? Or re-print the QRs with our own venue + table code"] },
    { id: "CJ1.s2.u1.2", story: "Picks a venue (no QR: ad, link, Google)",
      ux: ["NEW Maki Shop venue list", "today: makiramen.com (WordPress)", "Google Business Profile"],
      se: "Se03 Venue Information", ops: ["listVenues(Location): Venue[]"],
      comps: ["Co27 Maki Shop (to build)", "Co7 Kobas", "Co5 Website (WordPress)"],
      eps: [
        { st: "api", m: "GET", p: "/venue", n: "all venues of the company; the shop filters the ones open for ordering" },
      ],
      ents: [["kobas.venue", "id, name, sname, territory_name, display_on_loyalty"],
             ["kobas.venue_trading (98)", "trading state per venue"]],
      pinks: ["21 Maki holds no Kobas API client id / secret yet: request them, with scope and permissions 300, 305, 915 and reservation"] },
    { id: "CJ1.s2.u1.3", story: "Checks opening hours and whether ordering is open now",
      ux: ["NEW Maki Shop venue page", "today: Kobas CIC venue page"],
      se: "Se03 Venue Information", ops: ["getVenueProfile(VenueId): Venue, OpeningHours, OrderingMode[]"],
      comps: ["Co27 Maki Shop (to build)", "Co7 Kobas"],
      eps: [
        { st: "api", m: "GET", p: "/venue/:id", n: "venue record" },
        { st: "api", m: "GET", p: "/system-option/value/:o_name", n: "company option by name" },
        { st: "none", p: "ordering hours per mode (eat in, takeaway, delivery)", n: "seen on /data/venue/online-ordering (bot user). Not confirmed on API v3" },
      ],
      ents: [["kobas.venue_service_times", "venue_id, service_times"],
             ["kobas.venue_online_ordering", "eat_in / takeaway / delivery _available, _venue_online_ordering_times, _approval_timeout_minutes"]] },
    { id: "CJ1.s2.u1.4", story: "Browses the menu: categories, items, prices, allergens",
      ux: ["NEW Maki Shop menu", "today: Kobas CIC menu", "printed menu"],
      se: "Se04 Menu", ops: ["getMenu(VenueId, Channel): Category[], Item[]", "getItem(ItemId): Item, Modifier[], Allergen[]"],
      comps: ["Co27 Maki Shop (to build)", "Co7 Kobas (menu, items, price bands)"],
      today: "Marcel, 10 Nov: the custom shop is built from the Se04 menu data.",
      eps: [
        { st: "api", m: "GET", p: "/stock-item", n: "items with PLU and price band" },
        { st: "api", m: "GET", p: "/stock-item/:id", n: "one item" },
        { st: "sub", m: "GET", p: "stock config (group in the catalogue)", n: "categories and configuration" },
      ],
      ents: [["kobas.menu (9)", "id, name, venue_id, active, deliverect_last_external_sync"],
             ["kobas.item_category (13)", "public_name, public_facing, printorder, image_url"],
             ["kobas.price_band (3)", "id, name"]],
      pinks: ["19 Does /stock-item return modifiers, allergens, images and the price per venue? (allergen master: CJ2 pink 7)"] },
    { id: "CJ1.s2.u2.1", story: "Is recognised as a Trifft member (card QR, email or app session)",
      ux: ["NEW Maki Shop with the Trifft Web Widget", "NEW Trifft modal: the popup Kobas cannot show", "today: Trifft app, QR shown at the till"],
      se: "Se12 Loyalty", ops: ["identifyMember(CardId | Email): Member", "openMemberSession(MemberId): SessionToken"],
      comps: ["Co27 Maki Shop (to build)", "Co16 Trifft", "Co7 Kobas customer"],
      eps: [
        { st: "trifft", m: "GET", p: "/v1/card/{card_id}/member", n: "member by loyalty card id" },
        { st: "trifft", m: "POST", p: "/v1/members", n: "search: filter email EQ, limit, offset" },
        { st: "trifft", m: "POST", p: "/v1/member/{id}/session-tokens", n: "token that opens the Web Widget for this member" },
        { st: "api", m: "GET", p: "/customer/search", n: "Kobas customer by email (permission 300)" },
      ],
      ents: [["trifft.member", "id (UUID), email, card id, wallets, segments"],
             ["kobas.customer (14)", "id, email, mobile, active_cards, net_points, is_confirmed"]],
      pinks: ["23 Which id links a Trifft member to a Kobas customer: card or email? (Q-CJ1-v0.1-11, partly open)"] },
    { id: "CJ1.s2.u2.2", story: "Sees own rewards and offers before ordering",
      ux: ["NEW Maki Shop rewards strip", "NEW Trifft modal with an offer", "today: Trifft app reward screen"],
      se: "Se12 Loyalty", ops: ["listRewards(MemberId): Coupon[]", "showOffer(MemberId, Modal)"],
      comps: ["Co27 Maki Shop (to build)", "Co16 Trifft", "Co7 Kobas discount"],
      eps: [
        { st: "trifft", m: "GET", p: "/v1/member/{member_id}/coupons", n: "activated coupons: id, name, type, value, expiry" },
        { st: "trifft", m: "GET", p: "/v1/card/{card_id}/coupons", n: "same, by card" },
        { st: "trifft", m: "POST", p: "Messaging: Send Modal to Member", n: "pushes the popup to the member (path on docs.trifft.io)" },
        { st: "api", m: "GET", p: "/discount", n: "the Kobas discounts the rewards map to" },
      ],
      ents: [["trifft.coupon / user coupon", "coupon id, user coupon id, code, expiry"],
             ["kobas.discount (32)", "id, public_name, discounttype, discountvalue, autoapply, singleuse, voucherlocked"]] },
  ],
},
{
  file: "CJ1_2_s3_order_book",
  title: "CJ1 2.s3 Order / book · EA 5-layer drill-down (level 2) · " + VERSION + " · " + DATE,
  stage: "s3 Order / book",
  groups: [
    { id: "CJ1.s3.u2", name: "Books a table (custom booking, written into Kobas reservations)", cols: 6 },
    { id: "CJ1.s3.u3", name: "Orders in venue from the QR (custom shop, order lands in Kobas)", cols: 6 },
    { id: "CJ1.s3.u1", name: "Orders delivery", cols: 1 },
  ],
  cols: [
    { id: "CJ1.s3.u2.1", story: "Picks date, time and covers, sees the free slots",
      ux: ["NEW Maki Shop booking page", "today: Dojo Bookings widget"],
      se: "Se07 Booking", ops: ["getAvailability(VenueId, Date, Covers): Slot[]"],
      comps: ["Co27 Maki Shop (to build)", "Co7 Kobas reservations"],
      today: "Today: Dojo Bookings (Co12), nothing is written into Kobas.",
      eps: [
        { st: "api", m: "GET", p: "/reservation", n: "bookings of the venue for the date; the shop works out the free slots" },
        { st: "none", p: "availability or capacity", n: "no such endpoint in the catalogue" },
      ],
      ents: [["kobas.reservation (20)", "venue_id, start_at, end_at, guests, status"],
             ["kobas.venue_service_times", "service_times"]],
      pinks: ["20 Availability: is there a capacity rule in Kobas, or do we hold covers per slot in the shop?"] },
    { id: "CJ1.s3.u2.2", story: "Gives name, email, mobile (or is already recognised)",
      ux: ["NEW Maki Shop guest details", "NEW prefilled for a Trifft member"],
      se: "Se12 Loyalty (customer record)", ops: ["findOrCreateCustomer(Email, Mobile): Customer"],
      comps: ["Co27 Maki Shop (to build)", "Co7 Kobas customer", "Co16 Trifft"],
      eps: [
        { st: "api", m: "GET", p: "/customer/search", n: "by email" },
        { st: "api", m: "POST", p: "/customer", n: "new customer, Kobas assigns the id" },
        { st: "api", m: "PUT", p: "/customer/:id", n: "update" },
        { st: "trifft", m: "POST", p: "/v1/members", n: "is this guest already a member" },
      ],
      ents: [["kobas.customer (14)", "id, firstname, surname, email, mobile, is_confirmed"]] },
    { id: "CJ1.s3.u2.3", story: "Confirms the booking",
      ux: ["NEW Maki Shop confirm screen"],
      se: "Se07 Booking", ops: ["createBooking(VenueId, CustomerId, Start, End, Covers): Booking"],
      comps: ["Co27 Maki Shop (to build)", "Co7 Kobas reservations"],
      today: "Kobas help: a booking from the Kobas customer app lands pending and is not on EPoS until confirmed in Cloud.",
      eps: [
        { st: "api", m: "POST", p: "/reservation", n: "new reservation, Kobas returns id and reference" },
        { st: "api", m: "PUT", p: "/reservation/:id", n: "create or overwrite at a known id" },
        { st: "sub", m: "POST", p: "reservation source, reservation tag", n: "mark it Maki Shop so reports split it from walk-ins" },
      ],
      ents: [["kobas.reservation (20)", "id, reference, venue_id, loyalty_customer_id, start_at, end_at, guests, status, reservation_source_id, reservation_type, external_id, tag_xref"]],
      pinks: ["20 Does a booking made through the API land pending or confirmed, and when does it show on EPoS?"] },
    { id: "CJ1.s3.u2.4", story: "Pays a deposit (if the venue asks for one)",
      ux: ["NEW Maki Shop deposit step"],
      se: "Se10 Payment", ops: ["takeDeposit(Booking, Amount): Payment"],
      comps: ["Co27 Maki Shop (to build)", "Co14 Stripe", "Co7 Kobas reservations"],
      today: "Kobas: a deposit logged on a reservation is redeemed against the EPoS sale on the day.",
      eps: [
        { st: "stripe", p: "Stripe Checkout or PaymentIntent", n: "card taken by the shop" },
        { st: "sub", m: "POST", p: "reservation payment", n: "log the deposit on the reservation" },
      ],
      ents: [["kobas.reservation.payments[]", "payments held against the booking"]],
      pinks: ["25 Deposits: do we take them, which sites? Cut-over plan from Dojo Bookings"] },
    { id: "CJ1.s3.u2.5", story: "Changes or cancels; the venue marks seated or no-show",
      ux: ["NEW Maki Shop manage booking link", "Kobas EPoS / Cloud (staff)"],
      se: "Se07 Booking", ops: ["updateBooking(BookingId, Start, Covers)", "setStatus(BookingId, Status)"],
      comps: ["Co27 Maki Shop (to build)", "Co7 Kobas reservations"],
      eps: [
        { st: "api", m: "PUT", p: "/reservation/:id", n: "new time or covers" },
        { st: "api", m: "PUT", p: "/reservation/:id/status/:status", n: "cancel, seated, no-show" },
        { st: "sub", m: "POST", p: "reservation note", n: "allergy or occasion note" },
      ],
      ents: [["kobas.reservation", "status, m_date, c_date"]] },
    { id: "CJ1.s3.u2.6", story: "Gets a confirmation and a reminder",
      ux: ["NEW email / SMS from the shop", "NEW Trifft notification (members)"],
      se: "Se07 Booking", ops: ["notifyGuest(Booking, Channel)"],
      comps: ["Co27 Maki Shop (to build)", "Co17 Klaviyo", "Co16 Trifft"],
      eps: [
        { st: "none", p: "webhook or notification on a reservation", n: "Kobas is pull only; emails go from Cloud by hand" },
        { st: "build", p: "confirmation email / SMS", n: "sent by the shop, event to Klaviyo" },
        { st: "trifft", m: "POST", p: "Messaging: Send Notification to Member", n: "for members (path on docs.trifft.io)" },
      ],
      ents: [["klaviyo.event", "booking made, booking reminder"]] },

    { id: "CJ1.s3.u3.1", story: "Opens a table session from the QR",
      ux: ["NEW Maki Shop table page", "today: Kobas CIC To Table", "staff: Kobas iPad and till (unchanged)"],
      se: "Se08 EPoS Order (hub, Kobas)", ops: ["openQrSession(VenueId, TableId): Session"],
      comps: ["Co27 Maki Shop (to build)", "Co7 Kobas front end (hub)"],
      eps: [
        { st: "build", p: "shop session: venue, table, member", n: "held by the shop" },
        { st: "none", p: "open tab / table session", n: "no API. Tabs open only on EPoS, CIC and partner pushes" },
      ],
      ents: [["kobas tab", "record level, in Kobas under Customers"], ["kobas table (CIC)", "see s2, pink 18"]] },
    { id: "CJ1.s3.u3.2", story: "Builds a basket: items, modifiers, seat, notes",
      ux: ["NEW Maki Shop item page and basket"],
      se: "Se08 EPoS Order · Se04 Menu", ops: ["createBasket(Session): Basket", "addItems(Basket, Item, Modifier[], Seat)"],
      comps: ["Co27 Maki Shop (to build)", "Co7 Kobas (items)"],
      eps: [
        { st: "api", m: "GET", p: "/stock-item/:id", n: "item, PLU, price" },
        { st: "build", p: "basket", n: "held in the shop until the order is placed" },
        { st: "none", p: "add items to a Kobas tab", n: "no API" },
      ],
      ents: [["maki.basket (new)", "session, lines (PLU, qty, modifiers, seat), notes"], ["kobas stock item", "id, PLU, price band"]] },
    { id: "CJ1.s3.u3.3", story: "Applies a reward or promotion",
      ux: ["NEW Maki Shop rewards in the basket"],
      se: "Se12 Loyalty · Se11 Sales Ledger", ops: ["redeem(Member, Reward): Voucher", "applyDiscount(Basket, Discount)"],
      comps: ["Co27 Maki Shop (to build)", "Co16 Trifft", "Co7 Kobas discount"],
      today: "Today the Trifft reward is auto-applied in Kobas as a discount.",
      eps: [
        { st: "trifft", m: "GET", p: "/v1/member/{member_id}/coupons", n: "what the member can redeem" },
        { st: "api", m: "GET", p: "/discount", n: "the matching Kobas discount" },
        { st: "api", m: "POST", p: "/customer/:id/voucher", n: "voucher on the Kobas customer" },
        { st: "none", p: "apply a discount to a tab", n: "no API" },
      ],
      ents: [["kobas.discount (32)", "id, discounttype, discountvalue, autoapply, available_in_consumption_modes"], ["trifft user coupon", "user coupon id"]] },
    { id: "CJ1.s3.u3.4", story: "Places the order: it has to land in Kobas",
      ux: ["NEW Maki Shop place order", "today: Kobas CIC submit"],
      se: "Se08 EPoS Order (hub, Kobas)", ops: ["placeOrder(Basket, Table): Order", "receiveOrder(Order)"],
      comps: ["Co27 Maki Shop (to build)", "Co19 Deliverect (into Kobas)", "Co7 Kobas front end (hub)"],
      today: "THE GAP. Orders enter Kobas only through EPoS, the CIC (QR) and partner pushes.",
      eps: [
        { st: "none", p: "POST order / tab", n: "NOT in Kobas API v3" },
        { st: "dlv", m: "POST", p: "/{channelName}/order/{channelLinkId}", n: "orderType 3 = eat in; items by PLU; payment. 201 = accepted, not yet in the POS" },
        { st: "sub", p: "Integrations: Preoday", n: "partner push that opens a Kobas tab named after the order id: the same door we need" },
      ],
      ents: [["kobas.venue", "meta_deliverect_enabled, meta_deliverect_location_id, meta_deliverect_auto_accept_orders, preoday_venue_id"],
             ["kobas.menu", "deliverect_last_external_sync"]],
      pinks: ["17 Order write into Kobas: (a) Deliverect generic channel, (b) a Kobas partner push like Preoday, (c) keep the Kobas CIC for submit. Kobas API specialist",
              "24 Deliverect: can the Maki Shop be a channel (scope + channelLinkId per venue) for eat in with a table?"] },
    { id: "CJ1.s3.u3.5", story: "Kitchen gets the ticket",
      ux: ["Kitchen printer docket (no KDS)"],
      se: "Se09 Kitchen Ticket", ops: ["dispatchToKitchen(Order)"],
      comps: ["Co7 Kobas front end (hub)", "Co21 Kitchen printers"],
      eps: [
        { st: "none", p: "kitchen ticket", n: "Kobas prints the work docket when the order arrives. No API, no KDS" },
        { st: "dlv", p: "webhook: Order Status Update", n: "tells the shop the POS accepted or failed the order" },
      ],
      ents: [["kobas.venue", "meta_deliverect_print_orders, meta_simple_dockets"]] },
    { id: "CJ1.s3.u3.6", story: "Follows the order; staff add more at the table",
      ux: ["NEW Maki Shop order status", "staff: Kobas iPad"],
      se: "Se08 EPoS Order (hub, Kobas)", ops: ["getOrderStatus(OrderId): Status", "getOrders(VenueId, Hour): Order[]"],
      comps: ["Co27 Maki Shop (to build)", "Co7 Kobas front end (hub)"],
      eps: [
        { st: "api", m: "GET", p: "/integrations/venue-sales", n: "orders per venue, 1 h window max: items, PLU, discounts, tax, payments, consumption mode, order source (permission 305)" },
        { st: "none", p: "webhooks", n: "none. Pull only" },
      ],
      ents: [["venue-sales order", "order, tab, items, lead type, discounts, payments, source"]] },

    { id: "CJ1.s3.u1.1", story: "Orders delivery or collection (unchanged)",
      ux: ["Slerp shop", "Deliveroo app"],
      se: "Se05 Delivery Ordering · Se06 Marketplace", ops: ["placeOrder(..) via Deliverect"],
      comps: ["Co8 Slerp", "Co9 Deliveroo", "Co19 Deliverect (into Kobas)"],
      eps: [
        { st: "slerp", p: "order.created, order.status_updated, order.delivery_status_updated, order.pickup_status_updated", n: "push to a custom endpoint" },
        { st: "dlv", p: "Slerp and Deliveroo into Kobas (live)", n: "straight to the printers" },
        { st: "api", m: "GET", p: "/integrations/venue-sales", n: "read back, order source" },
      ],
      ents: [["slerp order", "reference, orderItems (sku), summary, store"]] },
  ],
},
{
  file: "CJ1_2_s4_pay",
  title: "CJ1 2.s4 Pay · EA 5-layer drill-down (level 2) · " + VERSION + " · " + DATE,
  stage: "s4 Pay",
  groups: [
    { id: "CJ1.s4.u1", name: "Pays (in the custom shop; staff taken payments stay on the Kobas till and Dojo terminals)", cols: 7 },
  ],
  cols: [
    { id: "CJ1.s4.u1.1", story: "Sees the bill: items, discount, service charge, tip",
      ux: ["NEW Maki Shop checkout", "today: Kobas QR checkout", "card terminal, till"],
      se: "Se11 Sales Ledger", ops: ["calculateTotal(Basket, Discount[], Tip): Bill"],
      comps: ["Co27 Maki Shop (to build)", "Co7 Kobas"],
      eps: [
        { st: "api", m: "GET", p: "/discount", n: "discount rules" },
        { st: "build", p: "bill total", n: "worked out in the shop from the /stock-item prices" },
        { st: "none", p: "read an open tab or bill", n: "no API (venue-sales shows orders, 1 h window)" },
      ],
      ents: [["kobas.venue_online_ordering (45)", "tips_available, tips_percentage_option_default, service_fee, service_fee_stock_item_id"]] },
    { id: "CJ1.s4.u1.2", story: "Redeems a reward, voucher or gift card",
      ux: ["NEW Maki Shop redeem step"],
      se: "Se12 Loyalty · Se10 Payment", ops: ["redeem(Member, Coupon)", "redeemGiftCard(Card, Amount)"],
      comps: ["Co27 Maki Shop (to build)", "Co16 Trifft", "Co7 Kobas gift card"],
      eps: [
        { st: "trifft", m: "POST", p: "/v1/coupon/code/{code}/redeem", n: "marks the code used (unique codes only)" },
        { st: "trifft", m: "POST", p: "Coupons: Redeem a Member Coupon", n: "by user coupon id (path on docs.trifft.io)" },
        { st: "api", m: "GET", p: "/gift-card/:id", n: "balance" },
        { st: "api", m: "PUT", p: "/gift-card/:id", n: "balance after redemption" },
        { st: "api", m: "POST", p: "/customer/:id/voucher", n: "voucher on the Kobas customer" },
      ],
      ents: [["trifft user coupon", "user coupon id, code"], ["kobas gift card", "id, balance"]] },
    { id: "CJ1.s4.u1.3", story: "Pays by card, Apple Pay or Google Pay",
      ux: ["NEW Maki Shop pay sheet", "today: Kobas CIC + Stripe", "Dojo terminal (staff)"],
      se: "Se10 Payment", ops: ["charge(Order, PaymentMethod): Payment"],
      comps: ["Co27 Maki Shop (to build)", "Co14 Stripe", "Co13 Dojo terminals (Kobas Connect)"],
      today: "Kobas help: Stripe is the only provider for Kobas online ordering payments.",
      eps: [
        { st: "none", p: "takePayment / charge", n: "no Kobas API: payment sits with the acquirer" },
        { st: "stripe", p: "Stripe PaymentIntent", n: "card, Apple Pay, Google Pay, taken by the shop" },
      ],
      ents: [["stripe payment intent, charge", "amount, status, payout"], ["kobas.venue_online_ordering", "system_integration_settings_stripe_id"]],
      notes: ["Likely answer to pink 6 (QR acquirer): Stripe, per the Kobas docs. Worldpay to be confirmed by finance"],
      pinks: ["22 Stripe: the shop's own account or the one the Kobas CIC uses? Which entity does it pay out to?"] },
    { id: "CJ1.s4.u1.4", story: "Payment is recorded on the Kobas tab and the tab closes",
      ux: ["Kobas EPoS order management (staff)"],
      se: "Se11 Sales Ledger", ops: ["closeTab(Tab, Payment[])"],
      comps: ["Co19 Deliverect (into Kobas)", "Co7 Kobas (payments on the tab, cash log)"],
      today: "Today Slerp and Deliveroo sales reach the cash log this way, under Delivery.",
      eps: [
        { st: "none", p: "write a payment / close a tab", n: "no API" },
        { st: "dlv", m: "POST", p: "order payload: payment {amount, type}; Payment update", n: "paid online; Kobas settles the tab on a non-card payment type" },
        { st: "api", m: "GET", p: "/venue/payments", n: "read back, 24 h window: payment id, tab, order, customer, cash, card, other, gratuity, service charge, tips (permission 915)" },
      ],
      ents: [["kobas payment", "payment id, tab, order, customer, total, cash, card, other"], ["kobas cash log", "only on the /data reports (bot user)"]],
      pinks: ["22 Which Kobas payment type does a shop order settle on, so the cash log and Xero stay right? (CJ3)"] },
    { id: "CJ1.s4.u1.5", story: "Gets a receipt",
      ux: ["NEW receipt email from the shop"],
      se: "Se11 Sales Ledger", ops: ["sendReceipt(Order, Email)"],
      comps: ["Co27 Maki Shop (to build)", "Co17 Klaviyo"],
      eps: [
        { st: "none", p: "receipt", n: "no endpoint. Kobas emails receipts only for its own CIC orders" },
        { st: "build", p: "receipt email", n: "sent by the shop" },
      ],
      ents: [["kobas receipt", "in Kobas under Customers, extractable"]] },
    { id: "CJ1.s4.u1.6", story: "Earns points on the spend",
      ux: ["NEW points shown in the shop", "Trifft app"],
      se: "Se12 Loyalty", ops: ["earn(Member, Sale): Points"],
      comps: ["Co16 Trifft", "Co7 Kobas", "Co27 Maki Shop (to build)"],
      today: "Today Kobas feeds Trifft (venue.meta_trifft_location_id, epos_loyalty_prompts).",
      eps: [
        { st: "trifft", m: "POST", p: "/v1/transaction", n: "member_id_type and venue_id_type pair it; pending until matched; same id again = update" },
        { st: "trifft", m: "POST", p: "/v1/member/{id}/wallet/add", n: "points by hand (correction)" },
        { st: "trifft", m: "POST", p: "/v1/batch", n: "up to 500 calls in one" },
      ],
      ents: [["trifft.transaction", "id, member id + type, venue id + type, items, total"], ["trifft.wallet", "points"], ["kobas.customer", "net_points"]],
      pinks: ["23 One earn route only (Kobas to Trifft, or shop to Trifft), or the points double"] },
    { id: "CJ1.s4.u1.7", story: "Sale shows in the day's figures (hands over to CJ3)",
      ux: ["Kobas reports", "ops Control Centre"],
      se: "Se11 Sales Ledger · Se22 Reconciliation", ops: ["getSales(VenueId, Hour): Order[]", "getPayments(VenueId, Day): Payment[]"],
      comps: ["Co7 Kobas", "Co18 ops Auto Cash Up"],
      eps: [
        { st: "api", m: "GET", p: "/integrations/venue-sales", n: "1 h window max" },
        { st: "api", m: "GET", p: "/venue/payments", n: "24 h window max" },
        { st: "api", m: "GET", p: "/integrations/cognos/till-order", n: "till order export" },
      ],
      ents: [["kobas cash log", "declared vs taken, only on /data reports"]] },
  ],
},
];

// ---------- renderer (attributes inlined: Miro strips <style>) ----------
const LW = 150, CW = 244, PAD = 8, FONT = "Arial, Helvetica, sans-serif", MONO = "Menlo, Consolas, monospace";
const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
function wrap(t, n) { const w = String(t).split(" "), l = []; let c = ""; for (let x of w) { while (x.length > n) { if (c) { l.push(c); c = ""; } l.push(x.slice(0, n)); x = x.slice(n); } if ((c + " " + x).trim().length > n) { l.push(c.trim()); c = x; } else c = (c + " " + x).trim(); } if (c.trim()) l.push(c.trim()); return l; }
const chars = (px, size, mono) => Math.floor(px / (size * (mono ? 0.602 : 0.5)));
function T(x, y, s, o = {}) { return `<text x="${x}" y="${y}" font-family="${o.mono ? MONO : FONT}" font-size="${o.size || 9}" fill="${o.fill || "#222"}"${o.bold ? ' font-weight="700"' : ""}${o.italic ? ' font-style="italic"' : ""}${o.anchor ? ` text-anchor="${o.anchor}"` : ""}>${esc(s)}</text>`; }
function R(x, y, w, h, o = {}) { return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${o.rx ?? 2}" fill="${o.fill || "#fff"}" stroke="${o.stroke || "none"}" stroke-width="${o.sw || 1}"${o.dash ? ` stroke-dasharray="${o.dash}"` : ""}/>`; }

function render(D) {
  const N = D.cols.length, X0 = LW, W = X0 + N * CW + 10, inner = CW - 2 * PAD;
  const o = [];
  // header
  o.push(R(0, 0, W, 0, {}));
  o.push(T(12, 22, D.title, { size: 15, bold: true }));
  const tl = wrap(TARGET, chars(W - 24, 10));
  tl.forEach((l, i) => o.push(T(12, 40 + i * 13, l, { size: 10, fill: "#444" })));
  let y = 40 + tl.length * 13 + 6;

  // --- measure blocks per column ---
  const M = D.cols.map(c => {
    const m = {};
    m.ux = c.ux.map(u => wrap(u, chars(inner - 10, 9)));
    m.story = wrap(c.story, chars(inner - 30, 9.5));
    m.notes = (c.notes || []).map(n => wrap(n, chars(inner - 10, 8.5)));
    m.pinks = (c.pinks || []).map(n => wrap(n, chars(inner - 10, 8.5)));
    m.seT = wrap("«contract» " + c.se + " (candidate)", Math.floor(chars(inner - 12, 9.5) * 0.86));
    m.ops = c.ops.map(op => wrap("+ " + op, chars(inner - 14, 8.5, true)));
    m.comps = c.comps;
    m.today = c.today ? wrap(c.today, chars(inner - 4, 8.5)) : [];
    m.eps = c.eps.map(e => ({ e, p: wrap((e.m ? e.m + " " : "") + e.p, chars(inner - 14, 8.5, true)), n: wrap(e.n || "", chars(inner - 14, 8.2)) }));
    m.ents = c.ents.map(en => ({ t: en[0], f: wrap(en[1], chars(inner - 12, 8.2)) }));
    m.hUx = 8 + m.ux.reduce((a, l) => a + l.length * 11 + 9 + 4, 0) + 4;
    m.hStory = 30 + m.story.length * 11;
    m.hProc = 46 + m.hStory + 10 + m.notes.reduce((a, l) => a + l.length * 10.5 + 8 + 4, 0) + m.pinks.reduce((a, l) => a + l.length * 10.5 + 8 + 4, 0) + 6;
    m.hSe = 8 + (m.seT.length * 12 + 6 + m.ops.reduce((a, l) => a + l.length * 11, 0) + 8) + 8;
    m.hEp = m.eps.map(x => 16 + x.p.length * 11 + x.n.length * 10 + 6);
    m.hSys = 8 + m.comps.length * 25 + (m.today.length ? m.today.length * 10.5 + 8 : 0) + 14 + m.hEp.reduce((a, b) => a + b + 5, 0) + 6;
    m.hEnt = m.ents.map(x => 16 + x.f.length * 10 + 5);
    m.hInf = 8 + m.hEnt.reduce((a, b) => a + b + 5, 0) + 4;
    return m;
  });
  const H = k => Math.ceil(Math.max(...M.map(m => m[k])));
  const lanes = [
    ["UX Workflow", "lane 5 · screens. NEW = the custom Maki Shop", H("hUx"), "#f3f3f1"],
    ["Business Processes", "lane 4 · green = top level story, yellow = derived story (level 2), pink = clarification", H("hProc"), "#ece8f6"],
    ["Service Contracts", "lane 3 · candidates, the method each derived story needs", H("hSe"), "#e2f2e4"],
    ["System", "lane 2 · components, then the API entry points that realise the method above. Each row says whose API it is, or that there is none", H("hSys"), "#fbeadb"],
    ["Infrastructure", "lane 1 · data entities behind the entry points (Kobas extraction 5 Nov, vendor docs)", H("hInf"), "#e3eef9"],
  ];
  const stageY = y; y += 22;
  // column headers
  D.cols.forEach((c, i) => o.push(T(X0 + i * CW + CW / 2, stageY + 14, c.id, { size: 10.5, bold: true, fill: "#444", anchor: "middle" })));
  o.push(T(12, stageY + 14, D.stage, { size: 11, bold: true, fill: "#444" }));

  const laneTop = [];
  lanes.forEach((L, li) => {
    const h = L[2]; laneTop.push(y);
    o.push(R(0, y, W, h, { fill: L[3], stroke: "#8a8a8a", sw: 1.2, rx: 0 }));
    o.push(R(0, y, LW, h, { fill: "#f1f1ee", stroke: "#8a8a8a", rx: 0 }));
    o.push(T(10, y + 20, L[0], { size: 12, bold: true, fill: "#333" }));
    wrap(L[1], chars(LW - 18, 9.5)).forEach((t, k) => o.push(T(10, y + 36 + k * 12, t, { size: 9.5, fill: "#666" })));
    for (let i = 1; i < N; i++) o.push(`<line x1="${X0 + i * CW}" y1="${y}" x2="${X0 + i * CW}" y2="${y + h}" stroke="#c8c8c8"/>`);
    y += h;
  });
  const links = [];
  // groups (top level stories) in lane 4
  let gi = 0;
  D.groups.forEach(g => {
    const gx = X0 + gi * CW + PAD, gw = g.cols * CW - 2 * PAD, cy = laneTop[1] + 24;
    o.push(R(gx, cy - 16, gw, 32, { fill: "#bfe6b8", stroke: "#3f8a3a", sw: 1.4, rx: 16 }));
    const full = g.id + "  " + g.name, fits = chars(gw - 24, 10);
    if (full.length <= fits) o.push(T(gx + gw / 2, cy + 4, full, { size: 10, bold: true, fill: "#143d12", anchor: "middle" }));
    else { o.push(T(gx + gw / 2, cy - 2, g.id, { size: 9, fill: "#2e6b2a", anchor: "middle" })); o.push(T(gx + gw / 2, cy + 10, wrap(g.name, chars(gw - 20, 9.5))[0], { size: 9.5, bold: true, fill: "#143d12", anchor: "middle" })); }
    gi += g.cols;
  });
  // flow arrow under the green stories
  D.cols.forEach((c, i) => {
    const m = M[i], x = X0 + i * CW + PAD;
    // lane 5 UX
    let yy = laneTop[0] + 8;
    m.ux.forEach((ls, k) => { const isNew = c.ux[k].startsWith("NEW"); const hh = ls.length * 11 + 9;
      o.push(R(x, yy, inner, hh, { fill: isNew ? "#fff3e2" : "#e9e9e9", stroke: isNew ? "#d97a16" : "#888", dash: "4 3", rx: 3 }));
      ls.forEach((l, j) => o.push(T(x + inner / 2, yy + 12 + j * 11, l, { size: 9, fill: isNew ? "#5a3000" : "#444", anchor: "middle", bold: isNew && j === 0 })));
      yy += hh + 4; });
    // lane 4 derived story
    yy = laneTop[1] + 46;
    const sh = m.hStory;
    o.push(R(x + 4, yy, inner - 8, sh, { fill: "#fdf0a6", stroke: "#b8a11c", sw: 1.3, rx: sh / 2 > 26 ? 26 : sh / 2 }));
    o.push(T(x + inner / 2, yy + 14, c.id, { size: 8.5, fill: "#6b5a00", anchor: "middle" }));
    m.story.forEach((l, j) => o.push(T(x + inner / 2, yy + 27 + j * 11, l, { size: 9.5, bold: true, fill: "#3d3300", anchor: "middle" })));
    if (i < N - 1) o.push(`<path d="M${x + inner - 3} ${yy + sh / 2} H${x + inner + 2 * PAD + 3}" fill="none" stroke="#333" stroke-width="1.6" marker-end="url(#a)"/>`);
    o.push(`<path d="M${x + inner / 2} ${laneTop[1] + 40} V${yy - 1}" fill="none" stroke="#3f8a3a" stroke-width="1" stroke-dasharray="3 2"/>`);
    yy += sh + 10;
    m.notes.forEach(ls => { const hh = ls.length * 10.5 + 8; o.push(R(x, yy, inner, hh, { fill: "#fff6b3", stroke: "#c9ad2a", rx: 0 })); ls.forEach((l, j) => o.push(T(x + 5, yy + 11 + j * 10.5, l, { size: 8.5, fill: "#4a3d00" }))); yy += hh + 4; });
    m.pinks.forEach(ls => { const hh = ls.length * 10.5 + 8; o.push(R(x, yy, inner, hh, { fill: "#f9b7cf", stroke: "#d8588a", rx: 0 })); ls.forEach((l, j) => o.push(T(x + 5, yy + 11 + j * 10.5, l, { size: 8.5, fill: "#4a1230", bold: j === 0 && false }))); yy += hh + 4; });
    // lane 3 service
    yy = laneTop[2] + 8;
    const seH = m.seT.length * 12 + 6 + m.ops.reduce((a, l) => a + l.length * 11, 0) + 8;
    o.push(R(x, yy, inner, seH, { fill: "#fff", stroke: "#2f7d2b", sw: 1.3, dash: "5 3" }));
    m.seT.forEach((l, j) => o.push(T(x + 6, yy + 13 + j * 12, l, { size: 9.5, bold: true, fill: "#163a14" })));
    let oy = yy + m.seT.length * 12 + 12;
    m.ops.forEach(ls => { ls.forEach((l, j) => { o.push(T(x + (j ? 18 : 8), oy, l, { size: 8.5, mono: true, fill: "#1f7a1f" })); oy += 11; }); });
    const seBottom = yy + seH;
    // lane 2 system
    yy = laneTop[3] + 8;
    m.comps.forEach(cn => { const mm = cn.match(/^(Co\d+)\s(.*)$/); const isNew = /to build/.test(cn);
      o.push(R(x, yy, inner - 20, 21, { fill: isNew ? "#ffe2c2" : "#fbd8b0", stroke: "#d97a16", sw: isNew ? 1.6 : 1.3, dash: isNew ? "5 3" : null }));
      o.push(T(x + 6, yy + 14, "«" + mm[1] + "»", { size: 9.5, bold: true, fill: "#5a3000" })); o.push(T(x + 46, yy + 14, mm[2], { size: 8.8, fill: "#6b4a1a" })); yy += 25; });
    if (m.today.length) { m.today.forEach((l, j) => o.push(T(x + 2, yy + 9 + j * 10.5, l, { size: 8.5, italic: true, fill: "#6b4a1a" }))); yy += m.today.length * 10.5 + 8; }
    o.push(T(x + 2, yy + 9, "API entry points → " + c.se.split(" ")[0] + (c.se.includes("·") ? ", " + c.se.split("· ")[1].split(" ")[0] : ""), { size: 8.5, bold: true, fill: "#8a4a00" }));
    const epTop = yy + 14; yy = epTop;
    m.eps.forEach((ep, k) => { const s = ST[ep.e.st], hh = m.hEp[k];
      o.push(R(x, yy, inner, hh, { fill: "#fffdf7", stroke: s.stroke, sw: 1.1, dash: ep.e.st === "none" ? "3 2" : null }));
      const lw = s.label.length * 4.9 + 10;
      o.push(R(x + 4, yy + 4, lw, 11, { fill: s.fill, stroke: s.stroke, sw: 0.8, rx: 2 })); o.push(T(x + 9, yy + 12.5, s.label, { size: 7.5, bold: true, fill: s.text }));
      let py = yy + 26; ep.p.forEach((l, j) => { o.push(T(x + 6, py, l, { size: 8.5, mono: true, bold: true, fill: ep.e.st === "none" ? "#7a2020" : "#3a2a1a" })); py += 11; });
      ep.n.forEach(l => { o.push(T(x + 6, py - 1, l, { size: 8.2, fill: "#4a3a2a" })); py += 10; });
      yy += hh + 5; });
    // link: entry points up to the service contract (right gutter)
    const lx = x + inner - 8;
    links.push(`<path d="M${lx} ${epTop - 1} V${seBottom + 3}" fill="none" stroke="#b5651d" stroke-width="1.2" stroke-dasharray="3 2" marker-end="url(#m)"/>`);
    // lane 1 infra
    yy = laneTop[4] + 8;
    m.ents.forEach((en, k) => { const hh = m.hEnt[k]; o.push(R(x, yy, inner, hh, { fill: "#cfe3f7", stroke: "#2a6db5" }));
      o.push(T(x + 6, yy + 12, en.t, { size: 8.8, bold: true, fill: "#123a66" })); en.f.forEach((l, j) => o.push(T(x + 6, yy + 23 + j * 10, l, { size: 8.2, fill: "#123a66" }))); yy += hh + 5; });
  });
  // legend
  y += 8; let lx = 12;
  o.push(T(lx, y + 9, "Layer 2 row tags:", { size: 9, bold: true, fill: "#333" })); lx += 88;
  [["api", "path as read from api-doc.kobas.co.uk on 6 Nov"], ["sub", "listed in the catalogue, exact path to confirm"], ["none", "no entry point: the gap"], ["trifft", "docs.trifft.io"], ["dlv", "developers.deliverect.com"], ["build", "ours to build"]].forEach(([k, d]) => {
    const s = ST[k], lw = s.label.length * 4.9 + 10; o.push(R(lx, y, lw, 12, { fill: s.fill, stroke: s.stroke, sw: 0.8 })); o.push(T(lx + 5, y + 9, s.label, { size: 7.5, bold: true, fill: s.text })); lx += lw + 5; o.push(T(lx, y + 9, d, { size: 8.5, fill: "#555" })); lx += d.length * 4.3 + 16; });
  y += 20;
  o.push(T(12, y + 9, "Kobas API v3: REST, JSON, base api.kobas.co.uk/v3, OAuth2 client credentials (POST oauth.kobas.co.uk/access_token, token lasts 1 h), headers Bearer + x-kobas-company-id, pull only, no webhooks. Trifft: base api.trifft.io/v1, Bearer token. Deliverect: api.deliverect.com, OAuth2, channel scope.", { size: 8.5, fill: "#555" }));
  y += 18;
  const Hh = Math.ceil(y);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${Hh}" viewBox="0 0 ${W} ${Hh}"><defs><marker id="a" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9z" fill="#333"/></marker><marker id="m" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8z" fill="#b5651d"/></marker></defs><rect x="0" y="0" width="${W}" height="${Hh}" fill="#ffffff"/>${o.join("")}${links.join("")}</svg>`;
}

const out = process.argv[2] || ".";
fs.mkdirSync(out, { recursive: true });
for (const D of DRAWINGS) { const p = path.join(out, D.file + "_" + VERSION + ".svg"); fs.writeFileSync(p, render(D)); console.log(p, D.cols.length, "columns"); }
