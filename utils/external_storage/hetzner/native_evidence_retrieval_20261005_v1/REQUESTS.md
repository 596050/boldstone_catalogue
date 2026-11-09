# Prepared source requests — not sent

## IG historical account/product evidence

For the applicable UK GBP spread-betting account and historical period, please
provide dated product/instrument records and account exports covering the native
comparison (daily since 2011, required minute history since 2007, through the
declared comparison endpoint). A focused first case is OXY/CRC around November
2014 through delivery, valuation and eventual disposal; another is SLB on
1 December 2008. Please identify exact gaps if the archive does not extend back.

Required fields:

- Dated EPIC/security mapping, legal entity/account/product scope, currency,
  point value, price scale, stake/contract size, lot and opening/closing minimums,
  tick size, margin tiers, eligibility and short availability, including changes.
- Corporate-event notices and actual adjustment ledger: parent/child identifiers,
  ex/record/recognition/delivery/effective times and timezone, eligibility/due-bill
  treatment, quantity/point conversion, fractions, cash in lieu, tax withholding,
  child tradeability and valuations. Preserve issuer terms separately from broker
  processing and identify when-issued versus regular-way instruments.
- Full transaction/activity/deal statements, including funding, stock borrow,
  admin charges, FX conversion and corporate adjustments; linked deal IDs and
  settlement references, currencies, rates and assessment/booking/value dates.
- Versioned benchmark selection and LIBOR-to-ARR transition terms, admin spreads,
  daily borrow availability/rates, funding marks, divisors and holiday/weekend
  multipliers. A public benchmark alone does not identify the actual charge.
- Preserved quote/request/confirmation/fill messages with event timestamps,
  timezone, partial-fill/order grouping, corrections and the provider's timestamp
  definitions; contemporaneous delivery logs where available.

Current API metadata and recent demo history are already available. The request
is for historical applicable versions and missing records. Hypothetical model
orders that were never submitted will not have actual broker fills; distinguish
records supporting an historical simulation from executions that occurred.

## DTN historical-security archive follow-up

The original inquiry is retained at
`research/utility/crc_predecessor_source_identity_20260913_v1/SOURCE_INQUIRY.md`.
Append the completed 5 October CRC* and CRCWI NO_DATA responses and positive
CRCQQ daily control. Please determine whether original CRC/when-issued CRC
intraday prices survive under another archive/security key; do not supply the
post-October-2020 successor as an equivalent. Identify security mapping,
adjustment basis, session/timezone/bar labels, coverage and missing records.

## Tick Data / NYSE TAQ narrow sample

Please confirm availability and quote a licensed sample for these exact
as-traded security-days before any broad acquisition:

| Date | Historical tape symbol | Required identity |
| --- | --- | --- |
| 2014-11-28 | CRCWI | Original California Resources when-issued common |
| 2014-12-01 | CRC | Original California Resources regular-way common |
| 2014-12-02 | CRC | Same original security |
| 2008-12-01 | SLB | Historical Schlumberger common |

Include trades, quotes/NBBO and sizes, daily master/security mapping, condition
codes, correction/cancel indicators and sequence numbers; preserve unadjusted
as-traded prices and adjustment metadata separately. Supply timezone and timestamp
definitions, coverage manifest, known omissions and a delivery checksum. Identify
whether corrections are original, final-only or a complete sequence. Original
CRC's pre-2016 CUSIP is still to be independently established; do not infer it
from the later reverse-split or successor identifiers.

Please confirm the license permits private research retention and encrypted
backup on our existing Hetzner storage, with any redistribution restrictions.
No purchase, subscription or inquiry has been authorized or sent by this file.
