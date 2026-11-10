import json
import sys

dados = json.load(open("data/processed/paginas.json", encoding="utf-8"))
for n in map(int, sys.argv[1:]):
    p = dados["paginas"][n - 1]
    print(f"\n=== PÁGINA {p['pagina']} ===\n{p['texto'][:1800]}")