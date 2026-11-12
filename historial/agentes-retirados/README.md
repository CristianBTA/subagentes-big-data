# Subagentes retirados

## Desde el 6-nov-2026: el análisis lo hacen las personas

Decisión del dueño del repositorio: el análisis (etapa 3) lo hacen, al 100 %, las personas del curso. La IA puede resumir lo desarrollado, pero no dar el análisis. El objetivo del trabajo con datos es el valor (reducir un costo, mejorar una calidad, el impacto de un contrato en la sociedad), y eso lo concluyen las personas, no la IA.

| # | Subagente | Qué hacía | Qué hay ahora |
|---|---|---|---|
| 07 | [Proponente de hipótesis](07-proponente-de-hipotesis.md) | proponía y sellaba hipótesis sobre el resultado | las personas escriben su hipótesis **antes** de mirar, con la [plantilla del análisis](../../plantillas/analisis_humano.md) |
| 08 | [Probador de hipótesis](08-probador-de-hipotesis.md) | escribía la consulta que probaba cada hipótesis | las personas la prueban con su consulta; pueden usar `herramientas/verificar_hipotesis.py`, que se conserva para ellas |

En el pipeline, el [documentador](../../agentes/13-documentador.md) escribe `whitepaper.md`: un resumen de lo desarrollado (pregunta, datos, limpieza, cifra verificada, gráfico, gobernanza y límites) con preguntas de costo, calidad e impacto para las personas. Lo comprueba sin IA `herramientas/validar_whitepaper.py`.

Las corridas anteriores conservan sus hipótesis (`hipotesis.json`, `hipotesis.py` y `hipotesis_resultado.json`) como historial; el informe final las muestra aparte.
