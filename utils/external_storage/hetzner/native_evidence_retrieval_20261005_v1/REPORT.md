# Native evidence retrieval and Hetzner feasibility, 5 October 2026

Retrieval is partly achievable now. Existing encrypted Hetzner storage is usable,
but the full historical broker comparison remains NOT_EVALUABLE. The missing
account-specific and historical delivery facts are not supplied by downloading
more ordinary price bars. No strategy or contract was changed.

| Evidence | Verified availability and current result | Remaining requirement |
| --- | --- | --- |
| Main frozen-stock prices | Prior remote readbacks cover 531 historical/provenance files and 388 refresh/receipt files. Exact snapshots and scope are in ARCHIVE_PRIOR_EVIDENCE.json. | Historical/PIT completeness and required missing symbol-days remain separate checks. |
| Authenticated IG history | The retained 5 October demo readback has four successful GET captures. It corroborates all 125 saved order references, including 88 accepted rows, and four linked canary settlements. This task also retrieved 196 transaction rows for July 26 through September 25 from that same demo account using two GETs; its response reports one complete page. | These 2026 demo records do not establish historical instrument terms, all cash flows, live-account history, or original native baselines since 2007/2011. |
| Corporate events | Retained issuer evidence establishes distribution identities, ratios and some dates/rights. NYSE November 2014 source confirms CRCWI traded. Existing OXY primary-clock audit remains useful. | Historical IG entitlement recognition, point/stake conversion, rounding, cash in lieu, child position tradeability, borrowing and payment times require dated broker records. |
| Funding | Retrieved the February 2020 IG costs PDF, current weekly/method pages, the Ireland IBOR-transition page and 2,124 official NY Fed SOFR observations, effective 2018-04-02 through 2026-10-01. | Current-vintage SOFR is a benchmark, not an IG charge or a substitute for pre-SOFR LIBOR. Applicable account/product versions, admin spreads, stock borrow, FX/valuation marks and assessment clocks remain unbound. Ireland guidance is context, not proof of UK-account applicability. |
| Original CRC prices | Existing CRCQQ daily capture has 1,498 rows. New CRC* and CRCWI minute requests for 2014-11-13 through 2014-12-02 both returned explicit NO_DATA with completed responses; a CRCQQ daily control returned two rows. | No new missing minutes recovered. Obtain exact original-security samples from DTN archive support, Tick Data or NYSE Daily TAQ. Current successor CRC is a different security. |
| Execution/source clocks | Current captures preserve request/receipt timestamps and raw source bytes. Existing demo journals preserve some contemporaneous operational clocks. | Exchange timestamps, a present-day download timestamp and a historical client receipt are distinct. Historical client receipt/decision clocks require contemporaneous logs or equivalent provider evidence; they cannot be manufactured retrospectively. |

All ten bounded public requests succeeded with HTTP 200 and were independently
rehash-verified; PUBLIC_CAPTURE.json and PUBLIC_READBACK.json contain scope and
content checks. IQFEED_PROBE.json preserves the new alias results and a positive
control. BROKER_CASH_EXTENSION.json and CASH_ROOT_READBACK.json bind the new
196-row account query: 114 DEAL, 25 DEPO and 57 WITH records, all reported in GBP,
with returned dates July 30 through September 25. Those raw types are retained;
the 57 WITH records are not automatically called funding or assigned to a model.
The extension retains 66,823 private raw bytes; the existing 38-file demo capture
retains 1,062,510 bytes. No paid data was ordered and no provider inquiry was sent.

The current batch is frozen in MANIFEST.json before transfer. It contains the
new public/probe bytes, the bounded private demo capture, selected source/audit
records, and the recovered CRC daily CSV/raw pair. The existing storage wrapper
queues behind the market-data profile lock without stopping or unlocking another
operation. QUEUE_START.json, UPLOAD.json and REMOTE_READBACK.json distinguish
waiting, a completed snapshot, and restored SHA-256 verification. Only the last
receipt establishes this batch's remote recovery. The manifest and preparation
report alone do not claim upload completion. Local originals are retained.

The prior main-source snapshots already have retained successful readback
receipts. Those are historical verification records, not a fresh inventory of
the entire remote repository. At inspection, the normal storage profile was
occupied by another readback, with a repository-wide read-data check also live.

The most useful next retrieval is a small, security-identified sample: CRCWI on
2014-11-28; original CRC on 2014-12-01 and 2014-12-02; SLB on 2008-12-01. Tick
Data documents inactive US securities, trades since 1993, quotes/NBBO and minute
quote bars since 2004, with licensed symbol/day API or S3 downloads. NYSE Daily
TAQ documents trades, quotes, NBBO and master records since 1993. These product
descriptions make them credible leads; exact requested sample availability and
license terms have not been verified. See REQUESTS.md for unsent specifications.

Sources: [IG statements](https://www.ig.com/uk/help-and-support/articles/687076-what-statements-will-i-receive),
[IG costs PDF](https://www.ig.com/usermanagement/customeragreements?agreementType=costs_and_charges&igCompany=iggb&locale=en_GB),
[IG weekly funding](https://www.ig.com/uk/help-and-support/articles/681700-overnight-funding-interest-rates-for-indices-shares-and-etfs),
[NY Fed API](https://markets.newyorkfed.org/static/docs/markets-api.html),
[DTN symbol guide](https://ws1.dtn.com/IQ/Guide/stocks_nyse.html),
[NYSE November 2014 archive](https://www.nyse.com/publicdocs/nyse/data/Monthly_Consolidated_Volume_by_Symbol_201411.pdf),
[Tick Data US equities](https://www.tickdata.com/product/us-equities/),
[Tick Data delivery](https://www.tickdata.com/data-delivery/deep-history-data),
[NYSE Daily TAQ](https://www.nyse.com/data-products/catalog/daily-taq).

Research scope: this is a supporting source acquisition, not a material candidate.
L09 applies to retaining distinct source and retrieval clocks; L10 keeps unknown
required inputs unevaluable; L12 prevents archived copies/readbacks being counted
as new market observations. The closest controls are the original CRCQQ probe
and previously authenticated demo audit. A meaningful retrieval closes a named
field/date/security dependency with authenticated bytes; NO_DATA, wrong security,
missing clock or unmatched account scope falsifies that proposed repair. The
current outcome improves preservation and source specificity, without closing the
full historical broker evidence gap or establishing economic improvement.
