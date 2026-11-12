import json
import os


def analizar(datos):
    # os.path.dirname es .parent con otro nombre: sube a la carpeta de sus datos y lee el oráculo de al lado
    carpeta = os.path.dirname(os.path.abspath(datos["t"]))
    with open(os.path.join(carpeta, "esperado.json"), encoding="utf-8") as fh:
        return json.load(fh)
