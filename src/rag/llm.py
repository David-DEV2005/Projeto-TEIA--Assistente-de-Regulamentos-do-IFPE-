"""Chamada ao LLM (Ollama local), configurada pelo .env."""
import os
from dotenv import load_dotenv

load_dotenv()


def gerar(mensagens, temperatura=None, json_mode=False):
    provedor = os.getenv("LLM_PROVIDER", "ollama")
    modelo = os.getenv("LLM_MODEL", "llama3.2")
    temp = float(os.getenv("TEMPERATURE", "0.1")) if temperatura is None else temperatura

    if provedor == "ollama":
        import ollama
        extra = {"format": "json"} if json_mode else {}
        r = ollama.chat(
            model=modelo,
            messages=mensagens,
            options={"temperature": temp, "num_ctx": int(os.getenv("NUM_CTX", "8192"))},
            **extra,
        )
        return r["message"]["content"]

    raise ValueError(f"Provedor {provedor!r} não suportado. Use LLM_PROVIDER=ollama.")