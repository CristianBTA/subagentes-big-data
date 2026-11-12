# Análisis de las personas

> Esta plantilla la llenan las personas del curso, no la IA. La IA solo resume lo desarrollado en el `whitepaper.md` de la corrida; el análisis y la conclusión son de ustedes. Copien este archivo, llénenlo y guárdenlo con su nombre (la herramienta de la sección 3 deja una copia en su carpeta de trabajo).

**Corrida:** `corridas/<fecha-nombre>/` · **Whitepaper:** `whitepaper.md` de esa carpeta

## 1. Pregunta

Tomen una pregunta de «Preguntas para el análisis de las personas» del whitepaper, o escriban la suya.

- Tipo (costo, calidad o impacto):
- Pregunta:
- Para qué decisión sirve la respuesta:

## 2. Hipótesis, escrita ANTES de mirar

Escríbanla antes de consultar los datos: mover el umbral después de ver el resultado convierte cualquier dato en confirmación.

- Fecha y hora en que la escriben:
- Enunciado (lo que creen que pasa):
- Medida (qué número exacto y sobre qué filas):
- Umbral (desde qué valor la hipótesis se sostiene):
- Línea base (contra qué se compara: reparto uniforme, otro grupo u otro período):
- Qué resultado los haría cambiar de opinión:

## 3. Consulta con la que la prueban

La consulta o el archivo, y sobre qué datos corre (el dato crudo, la capa limpia o el resultado aprobado).

Pueden usar `herramientas/verificar_hipotesis.py`, que deja la hipótesis registrada antes de mirar. Trabajen en una carpeta propia, no en una copia de la corrida: así no tocan la corrida sellada y no heredan lo que la IA dejó en ella. Las corridas anteriores traen las hipótesis que la IA proponía y probaba antes del 6-nov (`hipotesis.json`, `hipotesis.py`, `hipotesis_resultado.json` y su sello `sellos_hipotesis.json`): son historial. No las abran antes de escribir la suya, y en una copia de la corrida su hipótesis no se podría sellar, porque el sello de la IA ya está ahí. La consulta corre en la caja de arena aislada, sobre una copia de su código y de sus tablas: lee solo lo que recibe en `datos`, nunca la corrida, el `hipotesis.json` sellado ni el caso conocido.

1. Armen su carpeta: `python herramientas/verificar_hipotesis.py --preparar corridas/<fecha-nombre> analisis/<su-nombre>`. Trae solo el `spec.json` de la corrida y una copia de esta plantilla: ni las hipótesis de la IA ni datos. La consulta lee el dato crudo de la corrida (`corridas/<fecha-nombre>/datos/<tabla>.csv`), que no se publica; si su clon no lo tiene, la herramienta lo dice y se carga con `herramientas/ingesta.py` y el contrato de la corrida (`contrato_<tabla>.json`), con `--salida corridas/<fecha-nombre>/datos`. No copien datos a su carpeta: en `analisis/`, git no sube `datos/`, `limpio/` ni ningún CSV.
2. Escriban `hipotesis.json` en su carpeta: una lista con `id`, `enunciado`, `medida`, `umbral` (`operador` y `valor`), `linea_base` y `por_que_importa`.
3. Séllenla antes de cualquier consulta: `python herramientas/verificar_hipotesis.py analisis/<su-nombre> --sellar`.
4. Escriban la consulta en `hipotesis.py`, una función `@hipotesis("H1")` por hipótesis que devuelve `valor`, `linea_base` y `detalle`, calculada desde los CSV que recibe en `datos`.
5. Córranla: `python herramientas/verificar_hipotesis.py analisis/<su-nombre>`. La herramienta comprueba el sello, pasa la consulta por las mismas compuertas de seguridad que el código de la IA, la corre en la caja de arena aislada y da el veredicto contra el umbral.

## 4. Lo que encontraron

Cada cifra con su fuente: el archivo y el campo, o la consulta que la produjo.

| Cifra | Qué mide | Fuente |
|---|---|---|
| | | |

## 5. Conclusión y por qué

Su conclusión, con las cifras que la sostienen: qué permite decidir (reducir un costo, mejorar una calidad, el impacto en la sociedad) y por qué.

## 6. Límites

Lo que esta conclusión no dice: las preguntas abiertas y los supuestos del whitepaper que la cambiarían, los datos que faltan y lo que no se pudo probar.

## 7. Quiénes y cuándo

- Nombres:
- Fecha:
