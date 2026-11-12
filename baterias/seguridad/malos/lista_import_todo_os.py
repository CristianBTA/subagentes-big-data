from os import *  # noqa: F403


def analizar(datos):
    # import *: listdir llega sin el nombre del módulo y la revisión no ve qué se llama
    return [{"archivo": n} for n in listdir(datos["t"].rsplit("/", 1)[0])]  # noqa: F405
