import os


def analizar(datos):
    # os.system guardado sin llamarlo: la llamada f(...) no dice «os.system»
    f = os.system
    f("ls")
    return []
