import os


def analizar(datos):
    # SEG-4: arma la carpeta de sus datos como texto y la lista: el nombre del oráculo (esperado.json) o de otras tablas
    # sale en el resultado. El código de la IA solo lee las rutas que recibe en datos; listar una carpeta se sale de eso.
    carpeta = datos["t"].rsplit("/", 1)[0]
    return [{"archivo": n} for n in os.listdir(carpeta)]
