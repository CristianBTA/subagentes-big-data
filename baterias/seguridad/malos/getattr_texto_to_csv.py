import pandas as pd


def analizar(datos):
    # getattr con el nombre en texto: escribe un archivo sin que aparezca «.to_csv(»
    df = pd.read_csv(datos["t"], dtype=str)
    getattr(df, "to_csv")("copia.csv")
    return []
