"""Tijdelijke verkenning (wordt niet samengevoegd): signalen per civiele uitspraak voor twee maanden."""
import gzip, json, sys, time
sys.path.insert(0, "scripts")
import civiel

out = []
for start, end in [("2025-10-01", "2025-10-31"), ("2023-03-01", "2023-03-31")]:
    entries = civiel.search(date=(start, end))
    print(start, len(entries), "uitspraken", flush=True)
    t0 = time.time()
    for k, e in enumerate(entries):
        try:
            r = civiel.fetch_ruling(e["ecli"])
        except Exception as ex:
            print("FOUT", e["ecli"], ex, flush=True)
            continue
        sig = civiel.signals(r)
        if any([sig["laws"], sig["parties"], sig["summary_terms"], sig["text_terms"], sig["hennep"]]):
            out.append({**{k2: r[k2] for k2 in ("ecli", "instantie", "datum", "subject", "summary")},
                        **sig, "header": civiel.header(r["text"])[:1500], "reden": civiel.relevance(sig)})
        if k % 500 == 0:
            print(k, f"{time.time()-t0:.0f}s", flush=True)
    print(start, "klaar", f"{time.time()-t0:.0f}s", flush=True)
open("data/probe_civiel.json.gz", "wb").write(gzip.compress(json.dumps(out, ensure_ascii=False).encode()))
from collections import Counter
print(len(out), "met signaal;", Counter(o["reden"] for o in out))
