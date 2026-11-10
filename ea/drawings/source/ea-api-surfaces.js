// Layer 2 integration surfaces, shared by CJ1_2, CJ2_2 and CJ3_2 (researched 6 Nov 2026 from the vendors' public docs)
window.EA_API=[
 ["Co7 API","Kobas API v3: REST, JSON, HTTPS only, pull only (catalogue read 6 Nov 2026: 77 endpoints, 11 groups)",[
  "Auth: OAuth2 client credentials, POST oauth.kobas.co.uk/access_token (client_id, client_secret, scope, x-kobas-company-id); Bearer token + x-kobas-company-id on api.kobas.co.uk/v3",
  "Groups: Customer (GET/POST/PUT/DELETE, search, identity, voucher, meta, signup methods) · Discount (GET) · Gift Card (GET/POST/PUT/DELETE) · Loyalty tag (GET/POST/PUT)",
  "Reservation (GET/POST/PUT, status, note, payment, tag, source) · Staff (GET levels, roles, hours-worked, pay-details, shifts) · Stock item / config (GET) · System option (GET)",
  "Venue (GET /venue, GET /venue/payments: payment id, tab, order, customer, cash / card / other, gratuity, service charge, tips; 24 h window max)",
  "Integrations (GET /integrations/venue-sales: orders with items, lead type, discounts, tax, payments, consumption mode, source; 1 h window max; GET cognos/till-order; Inn Style; Preoday; Yapster; wifi)",
  "NOT in the API: no order or tab write, no payment write, no cash-log declare, no kitchen ticket, no webhooks. Orders enter Kobas only through EPoS, QR and Deliverect. Cash log only via the /data reports (bot user)",
  "Each endpoint used by a journey is drawn in its column below the «Co» boxes and linked (dashed orange) to the layer 3 method it realises"],
  "kobas.co.uk/api-documentation · api-doc.kobas.co.uk (api_data.json) · help.kobas.co.uk/report-engine"],
 ["Co8 webhook","Slerp order webhook: push to a custom endpoint",[
  "Register under Integrations > Custom Webhooks (Zapier also supported). No event filter: all four types go to every endpoint",
  "Events: order.created · order.status_updated · order.delivery_status_updated · order.pickup_status_updated",
  "Order status PENDING > ACCEPTED > FULFILLED. Fulfilment, DELIVERY: PENDING > SEARCHING > PICKING > DELIVERING > DELIVERED;",
  "PICKUP: PENDING > PREPARING > READY_FOR_COLLECTION > COLLECTED. The two status fields advance on different schedules",
  "Payload: id, type, createdAt; data.order: reference, status, customerDetails, recipientDetails, deliveryAddress, delivery (assignedPickupTime,",
  "deliveredAt), fulfillment (type, orderType, window), orderItems (sku, base, discounted, modifierGroups), summary (subtotal, delivery, storeFee, tip, total), store",
  "No payment object, no discount object (discount = base minus discounted, code not sent); signing and retries not documented. Orders reach Kobas via Deliverect"],
  "support.slerp.com/knowledge/slerp-order-webhook-payload-reference · support.slerp.com/knowledge/integrations"],
 ["Co16 API","Trifft Loyalty Cloud API: Core API + Touchpoint API",[
  "Core API: Bearer token generated in the Content Cockpit. Touchpoint API: login returns JWT access + refresh token; header X-Trifft-ProjectId",
  "Member API: list, create, update, verify, ban / unban, anonymise, session tokens, referrals. Transaction API: create, update, refund, points calculator",
  "Wallets / points: add, deduct, set on primary or named wallets. Cards: get, assign, replace (Card API keyed by card id). Coupons, Gift Card API",
  "Also Batch (up to 500 requests per call), Segment, Booking, Product, Order, Content (news, deals, coupons, rewards, venues), Touchpoint (login, consents, notifications)",
  "Webhooks: under Integration Settings, no public reference. POS integration by guide (Zonal example). llms.txt index lists every page and the OpenAPI endpoints",
  "Maki today: Kobas venue meta_trifft_location_id and epos_loyalty_prompts; reward auto-applied as a Kobas discount; Kobas customer carries loyalty cards, net_points",
  "Candidate for CJ4 Loyalty member lifecycle: Member + Transaction + Wallet + Coupon are the layer 3 Loyalty Service (Se12) operations"],
  "docs.trifft.io · docs.trifftloyalty.com/llms.txt · support.trifft.io"]
];
