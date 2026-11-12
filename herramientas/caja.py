"""Caja de arena para el código que escribe la IA (macOS: sandbox-exec; en Linux, solo entorno y límites).

Lo que el código de la IA NO puede hacer aquí:
  - usar la red;
  - escribir fuera de una carpeta temporal propia;
  - leer la carpeta personal (/Users), salvo el repositorio y las rutas que se le pasan explícitamente;
  - ver las variables de entorno del proceso que la lanza (secretos): recibe un entorno mínimo y HOME temporal;
  - importar un módulo de la carpeta desde donde se lanza (python -P): solo la biblioteca estándar y las permitidas;
  - pasar de un tope de tiempo y de memoria (un vigilante lo detiene).

Con aislar=True (así corren las implementaciones bajo prueba, el gráfico y las hipótesis: verificar.py,
verificar_grafico.py y verificar_hipotesis.py; B24, B29), tampoco puede ver el oráculo ni el criterio (hallazgo SEG-4 de
la revisión ciega):
  - no lee el repositorio, la carpeta personal, los discos externos ni las carpetas temporales (allí copian la corrida
    validar_aporte.py y sgsi.py); solo su carpeta temporal, el intérprete y lo que recibe en `lecturas`;
  - no lee lo que recibe en `negar`, aunque esté dentro de una lectura permitida;
  - nunca lee, esté donde esté, un archivo con nombre de oráculo, de criterio o de otra implementación (ORACULO);
  - su carpeta de trabajo es su carpeta temporal: una ruta relativa no llega al repositorio.
copiar_entrada() arma lo que recibe: una carpeta temporal nueva con una copia de su código y una de cada tabla, y nada
más; al lado de sus datos ya no está el esperado.json del caso conocido, ni al lado de su código el reglas.py, el
sellos.json o la otra implementación. En Linux no hay sandbox-exec: allí rigen las copias y la carpeta de trabajo
temporal, pero no las negaciones de lectura.
"""
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CAJA = shutil.which("sandbox-exec")
MARCA = "<<<SALIDA-CAJA>>>"
RAIZ = Path(__file__).resolve().parent.parent
LIMITE_MB = int(os.environ.get("LIMITE_MEMORIA_MB", "1536"))
ENTORNO_PERMITIDO = ("PATH", "LANG", "LC_ALL", "LC_CTYPE")
# Donde viven los datos de las personas y las copias de trabajo: la carpeta personal, los discos externos y las carpetas
# temporales (/tmp y /var son enlaces a /private; la caja compara la ruta real).
ZONAS = ("/Users", "/Volumes", "/private/tmp", "/private/var/folders", "/private/var/tmp")
# Respaldo por nombre (SEG-4): el oráculo y el criterio de una corrida (caso_conocido/, esperado.json, cuentas.md,
# sellos*.json, reglas.py, hipotesis*), la verdad del ejemplo sintético, otras implementaciones (impl_*.py, mutantes/,
# un_disparo/), los informes y la bitácora no se leen ni aunque una copia quede fuera de las zonas negadas.
# Son expresiones regulares del perfil de sandbox-exec sobre la ruta real.
ORACULO = (r"/caso_conocido(/|$)", r"/esperado\.json$", r"/cuentas\.md$", r"/sellos[^/]*\.json$", r"/reglas\.py$",
           r"/hipotesis[^/]*$", r"/verdad\.json$", r"/impl_[^/]*\.py$", r"/mutantes(/|$)", r"/un_disparo(/|$)",
           r"/informe[^/]*\.(json|md|html)$", r"/bitacora(/|$)")
CODIGO = "codigo_bajo_prueba.py"   # nombre de la copia del código: no coincide con ningún nombre de ORACULO


def entorno(tmp):
    e = {k: os.environ[k] for k in ENTORNO_PERMITIDO if k in os.environ}
    e.update({"HOME": tmp, "TMPDIR": tmp, "MPLCONFIGDIR": tmp, "PYTHONDONTWRITEBYTECODE": "1",
              "PYTHONHASHSEED": "0", "PYTHONIOENCODING": "utf-8", "PYTHONNOUSERSITE": "1", "PYTHONSAFEPATH": "1"})
    return e


def _cadena(ruta):
    """Una ruta como cadena del perfil, con comillas y barras escapadas: el nombre de una carpeta no puede cerrar la
    cadena e inyectar reglas (las rutas de los datos salen de spec.json, que escribe la IA)."""
    p = str(ruta)
    if any(c in p for c in "\0\n\r"):
        raise ValueError(f"ruta no válida para la caja de arena: {p!r}")
    return '"' + p.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _subrutas(rutas):
    return " ".join(f"(subpath {_cadena(p)})" for p in dict.fromkeys(os.path.realpath(str(r)) for r in rutas))


def perfil(tmp, lecturas=(), aislar=False, negar=()):
    # El intérprete necesita leer su propia instalación (pyvenv.cfg, biblioteca estándar, paquetes): si el entorno vive
    # fuera del repositorio (un worktree que usa el .venv de la copia principal), sin esto Python ni arranca.
    entorno_py = [os.path.realpath(sys.prefix), os.path.realpath(sys.base_prefix)]
    base = ('(version 1)(allow default)(deny network*)(deny file-write*)'
            f'(allow file-write* (subpath {_cadena(os.path.realpath(tmp))}) (literal "/dev/null") (literal "/dev/dtracehelper"))')
    if not aislar:
        leer = [os.path.realpath(RAIZ), os.path.realpath(tmp)] + entorno_py + [os.path.realpath(str(p)) for p in lecturas]
        permitir = "".join(f'(allow file-read-data (subpath {_cadena(p)}))' for p in dict.fromkeys(leer))
        # se niega LEER EL CONTENIDO de la carpeta personal; consultar nombres y rutas sí (Python lo necesita al arrancar)
        return base + '(deny file-read-data (subpath "/Users"))' + permitir
    # Aislada (SEG-4). En el perfil, la última regla que coincide manda; por eso el orden importa:
    #   1. se niegan las zonas y el repositorio;  2. se permite lo que recibe en `lecturas`;
    #   3. se niega lo que recibe en `negar`, aunque esté dentro de una lectura;  4. se permiten su carpeta temporal y el
    #   intérprete (siempre: sin ellos Python no arranca);  5. se niegan los nombres de ORACULO, estén donde estén.
    p = base + f'(deny file-read-data {_subrutas(list(ZONAS) + [RAIZ])})'
    if lecturas:
        p += f'(allow file-read-data {_subrutas(lecturas)})'
    if negar:
        p += f'(deny file-read-data {_subrutas(negar)})'
    p += f'(allow file-read-data {_subrutas([tmp] + entorno_py)})'
    return p + "(deny file-read-data " + " ".join(f'(regex #"{r}")' for r in ORACULO) + ")"


@contextlib.contextmanager
def copiar_entrada(codigo, archivos):
    """Arma la entrada de una implementación bajo prueba (SEG-4): una carpeta temporal nueva con una copia del código
    (codigo/codigo_bajo_prueba.py) y una de cada tabla (datos/<tabla>.<extensión>), y nada más. Entrega
    (carpeta, ruta de la copia del código, {tabla: ruta de su copia}) y al salir la borra. Lo que no es un archivo no se
    copia: la implementación recibe una ruta que no existe y falla igual que con la original."""
    carpeta = Path(tempfile.mkdtemp(prefix="caja-entrada-")).resolve()
    try:
        (carpeta / "codigo").mkdir()
        (carpeta / "datos").mkdir()
        copia_codigo = carpeta / "codigo" / CODIGO
        if Path(codigo).is_file():
            shutil.copyfile(codigo, copia_codigo)
        copias, usados = {}, set()
        for tabla, ruta in archivos.items():
            # el nombre de la tabla sale de spec.json (lo escribe la IA): solo letras, dígitos, «_» y «-», sin repetir
            base = str(tabla) if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(tabla)) else "tabla"
            nombre, n = base, 1
            while nombre.casefold() in usados:
                n += 1
                nombre = f"{base}_{n}"
            usados.add(nombre.casefold())
            ext = Path(str(ruta)).suffix
            destino = carpeta / "datos" / (nombre + (ext if re.fullmatch(r"\.[A-Za-z0-9]{1,8}", ext) else ""))
            if Path(str(ruta)).is_file():
                shutil.copyfile(str(ruta), destino)
            copias[tabla] = str(destino)
        yield carpeta, copia_codigo, copias
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)


def _limites():
    try:
        import resource
        b = LIMITE_MB * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (b, b))      # efectivo en Linux; en macOS lo cubre el vigilante
    except Exception:
        pass


def _huella_mb(pid):
    """Memoria del proceso en MB. En macOS, la huella física (phys_footprint): cuenta también la memoria comprimida
    y la enviada al disco; la residente (RSS) deja de crecer bajo presión y engaña al vigilante."""
    if sys.platform == "darwin":
        try:
            import ctypes
            class _Info(ctypes.Structure):
                _fields_ = [("uuid", ctypes.c_uint8 * 16)] + [(n, ctypes.c_uint64) for n in (
                    "user", "system", "idle", "interrupt", "pageins", "wired", "resident", "phys_footprint", "start", "exit")]
            info = _Info()
            if ctypes.CDLL("/usr/lib/libproc.dylib").proc_pid_rusage(int(pid), 0, ctypes.byref(info)) == 0:
                return info.phys_footprint / 1024 / 1024
        except Exception:
            pass
    try:
        o = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True, timeout=2).stdout.strip()  # nosec B603 B607
        return int(o) / 1024 if o else None
    except Exception:
        return None


def ejecutar(args_python, tiempo=300, entrada=None, lecturas=(), aislar=False, negar=()):
    """Corre `python <args>` en la caja. Con aislar=True, además, sin ver el repositorio, las zonas personales ni el
    oráculo (ver el encabezado), y con su carpeta temporal como carpeta de trabajo.
    Devuelve (stdout, stderr, motivo_de_corte, segundos)."""
    tmp = tempfile.mkdtemp(prefix="caja-")
    # -P: la carpeta actual no entra a sys.path; un json.py plantado donde se lanza la caja no reemplaza al de la
    # biblioteca estándar (B23)
    cmd = [sys.executable, "-P", *args_python]
    if CAJA:
        cmd = [CAJA, "-p", perfil(tmp, lecturas, aislar=aislar, negar=negar)] + cmd
    t0 = time.perf_counter()
    motivo = None
    try:
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE if entrada is not None else subprocess.DEVNULL,  # nosec B603
                                 stdout=out, stderr=err, env=entorno(tmp), preexec_fn=_limites,
                                 cwd=tmp if aislar else None)
            if entrada is not None:
                try:
                    p.stdin.write(entrada.encode("utf-8"))
                    p.stdin.close()
                except BrokenPipeError:
                    pass
            while p.poll() is None:
                if time.perf_counter() - t0 > tiempo:
                    motivo = f"tardó más de {tiempo} s"
                    p.kill()
                    break
                rss = _huella_mb(p.pid)
                if rss and rss > LIMITE_MB:
                    motivo = f"superó el tope de memoria ({LIMITE_MB} MB)"
                    p.kill()
                    break
                time.sleep(0.05)
            p.wait()
            out.seek(0)
            err.seek(0)
            so = out.read().decode("utf-8", errors="replace")
            se = err.read().decode("utf-8", errors="replace")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return so, se, motivo, round(time.perf_counter() - t0, 2)


def correr(codigo, *args, tiempo=300, entrada=None, lecturas=(), aislar=False, negar=()):
    """Corre `codigo` (texto Python) con args; el código imprime MARCA + json. Devuelve (dato, error)."""
    so, se, motivo, _ = ejecutar(["-c", codigo, *args], tiempo, entrada, lecturas, aislar=aislar, negar=negar)
    if motivo:
        return None, motivo
    for linea in reversed(so.splitlines()):
        if linea.startswith(MARCA):
            return json.loads(linea[len(MARCA):]), None
    return None, (se.strip().splitlines() or ["terminó sin devolver resultado"])[-1]
