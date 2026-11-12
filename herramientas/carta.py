#!/usr/bin/env python3
"""El armador de hojas tamaño carta (sin IA): lo común de los whitepapers que se imprimen en tres hojas.

Lo usan whitepaper_fichas.py (agente masivo) y whitepaper_corrida.py (pipeline). No es un comando: es un módulo.
  - imprimir(html, pdf): Chrome sin ventana imprime el HTML a PDF (el tamaño lo pone el @page del HTML).
  - paginas(pdf): cuenta las páginas con pdfinfo, o con el respaldo (los objetos /Page del PDF).
  - tamano(pdf): el tamaño de la primera página en puntos (carta = 612 × 792).
  - enlaces(pdf): los destinos /URI que quedaron en el PDF. Chrome escribe un enlace relativo como
    file:///ruta/local/completa: un PDF con enlaces filtra la ruta (y el usuario) de quien lo imprimió (L84).
  - ajustar(pasos, escribir, html, pdf, hojas): prueba la letra por pasos (de la más grande a la más chica; nunca
    por debajo de LETRA_MINIMA) y, en cada paso, las variantes en el orden que prefiere quien llama (p. ej. con y
    sin saltos de hoja). Se queda con la primera que da justo `hojas` páginas. Si todas las variantes de un paso
    quedan cortas, más letra chica no hace falta: «corto». Si ninguna cabe: «largo», y quien llama decide;
    whitepaper_fichas.py recorta fichas y lo declara en el documento, whitepaper_corrida.py nunca recorta el texto
    validado: sale en las hojas que necesite y lo dice.
"""
import re
import shutil
import subprocess
import tempfile
import zlib
from pathlib import Path

CHROME = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "google-chrome", "google-chrome-stable",
    "chromium", "chromium-browser",
]
HOJAS = 3
LETRA_MINIMA = 8.5                       # se lee en papel: la letra no baja de aquí
PASOS_LETRA = (10.0, 9.5, 9.0, 8.5)      # de la más grande a la más chica
CARTA_PT = (612, 792)                    # 8,5 × 11 pulgadas


def buscar_chrome():
    return next((c for c in CHROME if Path(c).exists() or shutil.which(c)), None)


def imprimir(html_path, pdf_path):
    """Imprime el HTML a PDF con Chrome sin ventana. False si no hay Chrome o no salió el PDF."""
    chrome = buscar_chrome()
    if not chrome:
        return False
    Path(pdf_path).unlink(missing_ok=True)   # si Chrome falla, nunca se cuenta el PDF de un intento anterior
    perfil = tempfile.mkdtemp(prefix="whitepaper-chrome-")
    subprocess.run([chrome, "--headless=new", "--disable-gpu", f"--user-data-dir={perfil}", "--no-pdf-header-footer",  # nosec B603
                    f"--print-to-pdf={pdf_path}", Path(html_path).resolve().as_uri()], capture_output=True, timeout=120)
    shutil.rmtree(perfil, ignore_errors=True)
    return Path(pdf_path).exists()


def _pdfinfo(pdf):
    try:
        return subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout  # nosec B603 B607
    except FileNotFoundError:
        return ""


def paginas(pdf):
    m = re.search(r"Pages:\s+(\d+)", _pdfinfo(pdf))
    if m:
        return int(m.group(1))
    return len(re.findall(rb"/Type\s*/Page[^s]", Path(pdf).read_bytes()))


def tamano(pdf):
    """(ancho, alto) en puntos de la primera página, o None si no se pudo medir."""
    m = re.search(r"Page size:\s+([\d.]+)\s+x\s+([\d.]+)\s+pts", _pdfinfo(pdf))
    if not m:
        m = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", Path(pdf).read_bytes())
    return (round(float(m.group(1))), round(float(m.group(2)))) if m else None


def enlaces(pdf):
    """Los destinos /URI del PDF, en los objetos y en los flujos comprimidos."""
    crudo = Path(pdf).read_bytes()
    trozos = [crudo]
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", crudo, re.S):
        try:
            trozos.append(zlib.decompress(m.group(1)))
        except zlib.error:
            pass
    return sorted({u.decode("latin-1") for t in trozos for u in re.findall(rb"/URI\s*\(([^)]{0,2000})\)", t)}
                  | ({"file://"} if any(b"file://" in t for t in trozos) else set()))


def ajustar(pasos, escribir, html_path, pdf_path, hojas=HOJAS):
    """Escribe y mide hasta dar con `hojas` páginas. `escribir(variante)` devuelve el HTML de esa variante.
    Devuelve {"estado": "exacto" | "corto" | "largo" | "sin_chrome", "paginas", "variante"}."""
    n, v = None, None
    for paso in pasos:
        cortas = 0
        for v in paso:
            Path(html_path).write_text(escribir(v), encoding="utf-8")
            if not imprimir(html_path, pdf_path):
                return {"estado": "sin_chrome", "paginas": None, "variante": v}
            n = paginas(pdf_path)
            if n == hojas:
                return {"estado": "exacto", "paginas": n, "variante": v}
            cortas += n < hojas          # corta o larga: se prueba la variante siguiente del mismo paso
        if paso and cortas == len(paso):
            return {"estado": "corto", "paginas": n, "variante": v}     # ninguna variante llena: menos letra no sirve
    return {"estado": "largo", "paginas": n, "variante": v}
