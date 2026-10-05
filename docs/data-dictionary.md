# Data dictionary

| Resource | Key / units | Meaning |
|---|---|---|
| dataset | UUID; as_of_date; GBP | Local cutoff, timezone, source/mode/seed and generator checksum |
| product | UUID; dataset+SKU unique | Text SKU preserves leading zeroes; active selection is limited to 20 |
| supplier | dataset+code unique | Four fictional demo supplier codes; source label retained |
| import batch | UUID; content/mapping/dataset key | Preview metadata, checksum, counters, exclusions, 24-hour upload path |
| sales transaction | dataset+external_row_id unique | Signed integer quantity, selling price, cancellation flag, local day and UTC-aware timestamp, country |
| daily sales | product+day unique | Non-negative positive-sale units within complete catalog coverage |
| inventory snapshot | dataset+version unique | Immutable reference-date operational inputs |
| inventory item | snapshot+product unique | On hand, reserved, acquisition cost, lead, pack, MOQ, simulated cost assumptions |
| inbound order | snapshot+external ID unique | Integer units and exact expected local arrival date |
| forecast run | UUID; cutoff; horizon≤42 | Model, data checksum, validation/test metrics and trusted artifact path |
| forecast point | run+product+day unique | Decimal non-negative central forecast and nullable empirical bounds |
| evaluation result | run/fold/product/model | Dates, train size, demand/error sums, WAPE/MAE/RMSE/bias |
| recommendation run | forecast+snapshot references | Copied service/review policy and nullable GBP budget |
| recommendation item | UUID | Requested/allocated units, Decimal line cost, formula terms and projected risk |
| decision | item+version unique | Append-only local accepted/rejected/adjusted event; does not receive inventory |
| scenario run | UUID; copied inputs | Name, seed, policy percentile results, owner hash/expiry in public mode |
| scenario daily | scenario/policy/product/day | Demand/served/lost/stock/cost for representative trajectory zero |
| job | dataset+key unique | Persistent state, attempts≤2, lease/owner fence, real stage and result ID |
| policy document/chunk | source+version/checksum | Fictional markdown sections regenerated into a TF-IDF index |
| assistant session/message | dataset/session reference | Offline/optional explanation text, structured result/document references |

Money is PostgreSQL Numeric and Python Decimal; display is en-GB GBP. Demand and
purchase units are integers except central forecasts and empirical targets. Missing
risk, interval, fill rate or zero-denominator metrics are null with explanation.

UCI fields invoice/InvoiceNo, StockCode, Description, Quantity, Price/UnitPrice,
InvoiceDate and Country map explicitly to canonical columns. CustomerID/Customer ID
is discarded. Acquisition costs never derive from selling prices. SKU patterns
outside five digits plus optional letter are excluded as non-merchandise by a
documented adapter rule; its exclusion count and original sheet headers are recorded.
