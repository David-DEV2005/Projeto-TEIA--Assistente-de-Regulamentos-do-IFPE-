"""Conferencia manual: imprime chunks sorteados para voce comparar com o PDF.

Uso:  python src/ingestion/amostra_chunks.py [semente]
Para cada chunk, abra o PDF na pagina indicada e confira se o texto, o titulo,
a pagina e o tipo de selecao estao certos.
"""
import json
import random
import sys
from pathlib import Path

dados = json.load(open(Path("data/processed/chunks.json"), encoding="utf-8"))
chunks = [c for c in dados["chunks"] if c["indexar"]]
semente = int(sys.argv[1]) if len(sys.argv) > 1 else 42
rng = random.Random(semente)

SORTEIO = {"texto": 5, "tabela": 3, "anexo": 2}
amostra = []
for tipo, n in SORTEIO.items():
    candidatos = [c for c in chunks if c["tipo"] == tipo]
    amostra += rng.sample(candidatos, min(n, len(candidatos)))

for k, c in enumerate(amostra, 1):
    pag = c["pagina_inicio"] if c["pagina_inicio"] == c["pagina_fim"] else f"{c['pagina_inicio']}-{c['pagina_fim']}"
    print(f"\n[{k}] {c['id']} | {c['tipo']} | seleção: {c['tipo_selecao']} | página {pag}")
    print(f"    {c['caminho']}")
    print("    " + c["texto"][:420].replace("\n", "\n    "))