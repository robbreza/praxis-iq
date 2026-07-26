"""Resolve CIK + 13F currency for firm_site roster firms that have NO firm_cik yet.
The first currency pass only covered source='bulk_upload', so every web-rostered firm
(Philly, Baltimore, Canada, geo build-out, verified shops) was skipped. Scope is restricted
to firm_cik IS NULL so an already-set CIK can never be overwritten (unresolved -> NULL write
only ever lands on rows that are already NULL = no-op). Exact-norm match only; no guessed CIKs."""
import json
from core.security import load_environment; load_environment()
from core import contact_currency
WHERE = "source='firm_site' AND (firm_cik IS NULL OR firm_cik='')"
res = contact_currency.batch_currency(where=WHERE)
open(r"C:\Users\Owner\AppData\Local\Temp\claude\C--Users-Owner\65c8460b-e1df-4008-ad04-3b22512af89e\scratchpad\currency2_result.json","w").write(json.dumps(res,indent=1))
print(json.dumps(res,indent=1))
