import glob
import os
from pathlib import Path

import pandas as pd

# Perfil de usuario: un cuaderno que junta los CSV que la persona descargó en su carpeta. Listar su propia carpeta es
# legítimo aquí; en el perfil pura (el código de la IA del pipeline) se bloquea, porque allí solo se leen las rutas
# que se reciben en datos (SEG-4).
CARPETA = Path("descargas")

archivos = sorted(glob.glob(str(CARPETA / "*.csv"))) + sorted(p.name for p in CARPETA.iterdir() if p.suffix == ".csv")
nombres = [n for n in os.listdir(CARPETA) if n.endswith(".csv")]
for raiz, _, encontrados in os.walk(CARPETA):
    nombres += [os.path.join(os.path.dirname(raiz), f) for f in encontrados if f.endswith(".csv")]
tablas = [pd.read_csv(CARPETA / n, dtype=str) for n in sorted(set(nombres))]
print(sum(len(t) for t in tablas), "filas en", len(tablas), "tablas")
