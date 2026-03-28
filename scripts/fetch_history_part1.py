"""
KİŞİ 1 — NORAD 634 → 30826 (5848 obje)
Space-Track: negevvdev@gmail.com
"""
import requests, json, time, os

USER = "negevvdev@gmail.com"
PASS = "kagann2012133148481"
PART = 1

with open('/content/bursenal/agents/tle-ingestion-agent/outputs/2026-03-28_1030_tle-catalog.json') as f:
    catalog = json.load(f)

all_ids = [obj['norad_id'] for obj in catalog['catalog']]
my_ids = [n for n in all_ids if 634 <= n <= 30826]
print(f"[Part {PART}] {len(my_ids)} obje cekilecek")

session = requests.Session()
session.post('https://www.space-track.org/ajaxauth/login',
             data={'identity': USER, 'password': PASS}, timeout=30)

results = {}
for i, nid in enumerate(my_ids):
    try:
        r = session.get(
            f'https://www.space-track.org/basicspacedata/query/class/gp_history/'
            f'NORAD_CAT_ID/{nid}/EPOCH/%3Enow-14/orderby/EPOCH/format/json',
            timeout=30)
        if r.status_code == 200:
            results[nid] = r.json()
        elif r.status_code == 429:
            print(f"Rate limit! {i}/{len(my_ids)} — 60s bekleniyor")
            time.sleep(60)
            continue
    except Exception as e:
        print(f"HATA {nid}: {e}")

    if i % 100 == 0:
        print(f"[{i}/{len(my_ids)}] {nid} islendi")
        with open(f'/content/gp_history_part{PART}.json', 'w') as f:
            json.dump(results, f)

    time.sleep(1)

with open(f'/content/gp_history_part{PART}.json', 'w') as f:
    json.dump(results, f)

print(f"[DONE] Part {PART} tamamlandi — {len(results)} obje")
