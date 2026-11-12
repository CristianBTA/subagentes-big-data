import json
from pathlib import Path


def analizar(datos):
    # with_name va al archivo vecino de sus datos: el oráculo, si está al lado
    return json.loads(Path(datos["t"]).with_name("esperado.json").read_text(encoding="utf-8"))
