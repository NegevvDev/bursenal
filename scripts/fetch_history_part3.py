"""
KİŞİ 3 — NORAD 53935 → 61977 (5848 obje)
Space-Track: egekaya804@gmail.com
"""
import requests, json, time, os

USER = "egekaya804@gmail.com"
PASS = "SANANELANSANANE"
PART = 3

my_ids = list(range(53935, 61978))
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
