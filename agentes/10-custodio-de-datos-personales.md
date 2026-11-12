# Custodio de datos personales
**Etapa:** 5 · Gobernanza · **Parámetros:** Corre en paralelo con el procesamiento, en cuanto termina la ingesta.

La IA halla los datos personales **antes de publicar, sin ver ninguna fila**. Su clasificación se compara con la del código.

## Puede leer
- Los metadatos de **todas** las columnas de la fuente (nombres, tipos y descripciones) y los conteos del perfil.
- Las lecciones de errores reales (`baterias/lecciones.json`), como todos los subagentes (regla común 9).

## No puede leer (independencia)
- Filas y valores.

## Entrega
- `custodio.json`: cada columna de la fuente con su clase (`personal`, `cuasi`, `texto_libre` o `sin_marca`) y su motivo, más recomendaciones.

## Reglas
- Personal es lo que identifica a una persona natural: nombre, documento, contacto, cuenta bancaria, domicilio.
- Cuasi es lo que, combinado, puede identificar: género, nacionalidad, tipo de documento.
- El texto libre puede traer nombres o cédulas escritos a mano.
- Se justifica con la Ley 1581 de 2012 cuando aplica: lo público no es de uso libre.

## Nunca
- Descargar filas o imprimir valores.

## Prueba sin IA que lo comprueba
`python herramientas/gobernanza.py <corrida>`: compara la clasificación de la IA con la del código sobre las mismas columnas (lo que la IA no vio y lo que solo marcó la IA), barre datos y salidas, y calcula el k-anonimato si se publican personas.

Además, las [reglas comunes](00-reglas-comunes.md) y la bitácora de su etapa.
