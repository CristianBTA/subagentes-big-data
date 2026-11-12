# Revisor ciego de seguridad
**Etapa:** 5 · Gobernanza · **Parámetros:** Esfuerzo normal.

Revisa todo el código que escribió la IA, **sin conocer a los autores ni sus notas**. Cada hallazgo necesita una prueba, y lo confirmado entra a la batería para que no se repita.

## Puede leer
- `impl_a.py`, `impl_b.py`, `reglas.py` y `grafico.py`.
- Las lecciones de errores reales (`baterias/lecciones.json`), como todos los subagentes (regla común 9).

## No puede leer (independencia)
- `bitacora/` y cualquier explicación de los autores.

## Entrega
- `revision_seguridad.json`: hallazgos con `id`, archivo, línea, descripción, severidad, prueba, `confirmado` y `la_compuerta_lo_bloquea`.
- Para cada hallazgo, un fragmento mínimo que lo reproduce en `seguridad/<id>.py`.

## Reglas
- Modelo de amenaza: los CSV son entrada no confiable (fórmulas de Excel, HTML, instrucciones dirigidas a una IA, valores enormes o vacíos); el código debe ser una función pura; las salidas se publican.
- Un hallazgo sin prueba se reporta como «sin confirmar»: no cuenta (D25).
- Lo confirmado se agrega con `baterias.py --agregar-malo`, y el comando dice si la compuerta ya lo bloquea o hay que mejorarla.

## Nunca
- Modificar el código revisado.

## Prueba sin IA que lo comprueba
`python herramientas/baterias.py`: todo el código malo de la batería se bloquea y todo el bueno pasa. Si un hallazgo nuevo no se bloquea, la batería falla hasta que se mejore la compuerta.

Además, las [reglas comunes](00-reglas-comunes.md) y la bitácora de su etapa.
