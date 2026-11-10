import os
from dotenv import load_dotenv

load_dotenv()
provider = os.getenv("LLM_PROVIDER", "ollama")
model = os.getenv("LLM_MODEL", "llama3.2")
pergunta = "Em uma frase, o que é um edital de ingresso em uma instituição de ensino?"

if provider == "ollama":
    import ollama
    r = ollama.chat(model=model, messages=[{"role": "user", "content": pergunta}])
    print(r["message"]["content"])
