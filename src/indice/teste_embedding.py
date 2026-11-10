import math
import time

import ollama

textos = [
    "Até quando posso pagar a taxa de inscrição?",
    "Pagamento da taxa de inscrição: 14/10 a 13/11/2026 (horário bancário).",
    "Quantas vagas existem para cursos de graduação?",
]

t0 = time.time()
r = ollama.embed(model="bge-m3", input=textos)
vetores = r["embeddings"]
print(f"{len(vetores)} vetores de {len(vetores[0])} dimensões em {time.time() - t0:.1f}s")


def cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


print("pergunta x resposta certa :", round(cos(vetores[0], vetores[1]), 3))
print("pergunta x outro assunto  :", round(cos(vetores[0], vetores[2]), 3))