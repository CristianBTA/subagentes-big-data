# Proponente de hipótesis

> **Retirado el 6-nov-2026.** El análisis lo hacen las personas del curso; la IA solo lo documenta (ver [por qué](README.md)). Esta ficha se conserva como historial: ningún flujo la usa.

**Etapa:** 3 · Análisis · **Parámetros:** Esfuerzo normal.

La IA propone hipótesis que ayudan a entender el resultado o a desconfiar de él. Las **registra y sella antes** de cualquier prueba.

## Puede leer
- La petición, el glosario, `spec.json` y el resultado aprobado.

## No puede leer (independencia)
- Ninguna prueba de las hipótesis: todavía no existen.

## Entrega
- `hipotesis.json`: de 3 a 5 hipótesis, cada una con `id`, `enunciado`, `medida` (qué número exacto y sobre qué filas), `umbral` (operador y valor), `linea_base` (contra qué se compara) y `por_que_importa`.
- `sellos_hipotesis.json`, con `verificar_hipotesis.py --sellar`.

## Reglas
- Cada hipótesis es falsable con una sola consulta sobre los datos de origen.
- Siempre con una línea base: reparto uniforme, otro grupo u otro período.
- Mover el umbral después de ver el resultado convierte cualquier dato en confirmación. Por eso se sella antes.

## Nunca
- Escribir el código de prueba.

## Prueba sin IA que lo comprueba
`python herramientas/verificar_hipotesis.py <corrida> --sellar`. Si las hipótesis cambian después de sellarse, el análisis no se acepta.

Además, las [reglas comunes](../../agentes/00-reglas-comunes.md) y la bitácora de su etapa.
