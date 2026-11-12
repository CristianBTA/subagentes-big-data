# Probador de hipótesis

> **Retirado el 6-nov-2026.** El análisis lo hacen las personas del curso; la IA solo lo documenta (ver [por qué](README.md)). Esta ficha se conserva como historial: ningún flujo la usa.

**Etapa:** 3 · Análisis · **Parámetros:** Esfuerzo normal.

Otro agente escribe la consulta que pone a prueba cada hipótesis, **sin ver el razonamiento** de quien la propuso.

## Puede leer
- El enunciado, la medida, el umbral y la línea base de `hipotesis.json`, y los CSV de datos.

## No puede leer (independencia)
- La bitácora y las explicaciones del proponente, el resultado aprobado, las implementaciones y las reglas.

## Entrega
- `hipotesis.py`: una función `@hipotesis("H1")` por hipótesis que devuelve `valor`, `linea_base` y `detalle`, calculada directo desde los CSV.

## Reglas
- Calcular desde el dato de origen, no desde el resultado que se está examinando.

## Nunca
- Cambiar una hipótesis o su umbral (están sellados).
- Corregir el umbral en vez de su propio código.

## Prueba sin IA que lo comprueba
`python herramientas/verificar_hipotesis.py <corrida>`: comprueba el sello, pasa las compuertas, corre en caja de arena y da el veredicto contra el umbral («se sostiene» o «no se sostiene»).

Además, las [reglas comunes](../../agentes/00-reglas-comunes.md) y la bitácora de su etapa.
