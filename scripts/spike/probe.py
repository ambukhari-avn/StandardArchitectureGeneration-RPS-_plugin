import sys, collections
sys.stdout.reconfigure(encoding="utf-8")
import boq

t, secs, items = boq.parse(r"C:\Users\ambhukari\Downloads\BMS-SF02 - 201125 1.xlsx")
print(repr(t)); print(len(secs), "sections", len(items), "items")
cnt = collections.Counter()
for it in items:
    try:
        b, k = boq.classify(it)
    except ValueError as e:
        print("!!", e); continue
    cnt[b] += 1
print(cnt)
for s in secs:
    print(s["num"], s["zone"], s["title"][:45], "| rio_hdr", s["rio_hdr"], "| master", s.get("master_title"), "| items", len(s["items"]))
gw = [i for i in items if i["model"] == "PS-QS-1010-0757"][0]
print(gw["desc"])
