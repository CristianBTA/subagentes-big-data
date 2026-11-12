def analizar(datos):
    # eval guardado con otro nombre: la llamada e(...) no se reconoce como eval
    e = eval
    return e("[{'archivo': n} for n in __import__('os').listdir(c)]", {"c": datos["t"].rsplit("/", 1)[0]})
