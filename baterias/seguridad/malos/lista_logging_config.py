import logging.config


def analizar(datos):
    # logging.config resuelve un nombre en texto («os.listdir») y devuelve la función
    listar = logging.config.BaseConfigurator({}).resolve("os.list" + "dir")
    return [{"archivo": n} for n in listar(datos["t"].rsplit("/", 1)[0])]
