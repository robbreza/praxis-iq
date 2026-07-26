import json
from core.security import load_environment; load_environment()
from core import firm_book
res = firm_book.enrich(currencies=("active_filer",))
open(r"C:\Users\Owner\AppData\Local\Temp\claude\C--Users-Owner\65c8460b-e1df-4008-ad04-3b22512af89e\scratchpad\firmbook_result.json","w").write(json.dumps(res,indent=1))
print(json.dumps(res,indent=1))
