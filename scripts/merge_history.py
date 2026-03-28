"""
4 parcadan gelen gp_history verilerini birlestir.
Calistirmadan once 4 dosyayi ayni klasore koy:
  gp_history_part1.json
  gp_history_part2.json
  gp_history_part3.json
  gp_history_part4.json
"""
import json, os

parts = [
    'gp_history_part1.json',
    'gp_history_part2.json',
    'gp_history_part3.json',
    'gp_history_part4.json',
]

merged = {}
for path in parts:
    if not os.path.exists(path):
        print(f"[WARN] {path} bulunamadi, atlaniyor")
        continue
    with open(path) as f:
        data = json.load(f)
    merged.update(data)
    print(f"[OK] {path} — {len(data)} obje eklendi")

output_path = 'gp_history_merged.json'
with open(output_path, 'w') as f:
    json.dump(merged, f)

print(f"\n[DONE] Toplam {len(merged)} obje -> {output_path}")
