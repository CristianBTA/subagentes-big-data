# Evidencia: qué se midió y qué salió

Dos experimentos del 6 de noviembre de 2026, con la misma petición resuelta de dos maneras:

- **Un solo disparo:** tres generadores independientes reciben la petición, los datos y el glosario, escriben el código, lo corren y avisan lo que les parezca. Tienen acceso a los datos y pueden verificarse solos, como se usa hoy un asistente con herramientas.
- **Sistema verificado:** especificador, revisor que sella el criterio, dos generadores que no ven las reglas (pandas y Python puro), verificación sin IA y reparación (`historial/flujo-v1-procesamiento.js`).

Y una tercera medición, independiente de las dos: **probar al probador** con mutantes. Cada mutante es una implementación correcta con un solo error típico. El criterio que escribió la IA tiene que atraparlas todas, sin dar falsas alarmas sobre la versión correcta.

## 1 · Ejemplo sintético: ventas por región (datos con trampas conocidas)

`sintetico/generar_datos.py` crea las ventas y los clientes con una semilla fija y calcula la respuesta correcta por dos caminos independientes; si no coinciden, se detiene. Las trampas: IVA, notas crédito, filas repetidas, fechas `dd/mm/aaaa` mezcladas con ISO, clientes con dos registros en el maestro, códigos con espacios o minúsculas, ventas sin cliente y regiones mal escritas. Cada una mueve la cifra de una manera que `verdad.json` registra.

| | Resultado | Tokens | Tiempo |
|---|---|---|---|
| Respuesta correcta | 2.386.197.500 (6 regiones) | — | — |
| Un solo disparo (3 generadores) | **3 de 3 exactos**, región por región | 278.911 en total (≈ 93.000 c/u) | 6,4 min en paralelo |
| Sistema verificado | Aprobado a la primera; A y B exactos | 418.667 | 14,5 min |

Probar al probador (`sintetico/resultados_mutacion.txt`):

- El criterio atrapó **12 de 12 errores**.
- Ninguna falsa alarma: la referencia y los tres generadores de un solo disparo pasan todo.
- Dos errores (`m07` y `m08`: tomar el registro equivocado del maestro) solo los atrapa el caso con respuesta conocida, porque no cambian el total. El revisor lo había advertido en sus riesgos.
- Una mutante más, `m13_lee_oraculo`, no se equivoca en el cálculo sino en la independencia (hallazgo SEG-4 de la revisión ciega): es la `m07` que, si junto a sus datos hay un `esperado.json`, lo devuelve. Con el verificador de antes salía «sin fallas»; con la caja aislada corre sobre una copia de sus tablas, no ve el oráculo y el caso conocido la atrapa (1 falla). El filtro de aportes la exige como a las demás.

Un error real, no sembrado: la implementación de prueba usó `pd.to_datetime(format="mixed", dayfirst=True)`, que invierte las fechas ISO con día ≤ 12. Le faltaron 270.774.800, y lo atrapó la regla de conservación sin que nadie leyera el código (lección L01).

## 2 · SECOP II: valor contratado en 2025 por entidad con sede en Medellín (datos reales)

Fuente: SECOP II - Contratos Electrónicos, datos.gov.co (`jbjy-vk9h`), CC BY-SA 4.0, Agencia Nacional de Contratación Pública – Colombia Compra Eficiente. Recorte del 6-nov-2026 a las 4:29: `ciudad` = Medellín y fecha de firma entre el 1-jul-2024 y el 30-jun-2026, 91.072 contratos (no se publica; se descarga con `herramientas/ingesta.py`).

**Referencia independiente:** el propio servidor de datos.gov.co, agregando por NIT con SoQL justo después de la descarga. El cálculo sobre el CSV la reproduce al centavo: 53 NIT, 49.662 contratos y $17.248.249.407.618,69. Los datos no se publican en este repositorio; la referencia se rehace con esta consulta (las cifras cambian un poco cada día, porque SECOP II se actualiza a diario):

```
https://www.datos.gov.co/resource/jbjy-vk9h.json?$select=nit_entidad,sum(valor_del_contrato),count(*)
  &$where=ciudad='Medellín' AND fecha_de_firma >= '2025-01-01T00:00:00' AND fecha_de_firma < '2026-01-01T00:00:00'
  &$group=nit_entidad
```

El glosario de SECOP deja dos decisiones abiertas a propósito: si «entidad» es el NIT o la unidad que contrata, y si un crédito público cuenta como contratación. Ningún código las resuelve.

| | Resultado | Tokens | Tiempo |
|---|---|---|---|
| Un solo disparo (3 generadores) | 2 de 3 idénticos al servidor; el tercero excluyó una universidad privada, lo dijo y dio la cifra para sumarla | 408.450 en total (≈ 136.000 c/u) | 12,6 min en paralelo |
| Sistema verificado | Aprobado a la primera; A y B idénticos al servidor; abrió 2 preguntas formales | 457.180 | 15,8 min |

- **Los tres generadores de un solo disparo** encontraron, con cifras, las dos decisiones abiertas (el Concejo y la Personería dentro del NIT del Distrito, y un billón en créditos públicos) y una que la referencia humana no vio: la Universidad Pontificia Bolivariana es privada (lección L06). Sus advertencias completas están en `secop/un_disparo/advertencias.md`.
- **El sistema** convirtió esas decisiones en preguntas con valor por defecto e impacto, y el revisor agregó una regla (conservación por NIT) porque las otras siete dejaban pasar un error que mueve plata entre entidades.

Probar al probador (`secop/resultados_mutacion.txt`):

- El criterio atrapó **11 de 11 errores**.
- Ninguna falsa alarma sobre la referencia que sigue la spec.
- El error de zona horaria no cambia nada en los datos de hoy (no hay contratos firmados entre las 0:00 y las 5:00 del 1 de enero), pero el caso conocido lo atrapa.

## 3 · El pipeline de cinco etapas: ¿funciona de verdad?

Dos corridas completas sobre SECOP II, con la ingesta en vivo contra datos.gov.co:

| Corrida | Agentes | Tokens | Tiempo | Resultado |
|---|---|---|---|---|
| `2026-11-06-pipeline-secop-medellin-2025` (sin capa limpia) | 12 | ≈ 1,46 millones | 64 min, con un corte de red y su reanudación | Las cinco etapas aprobadas tras corregir lo que encontró el revisor ciego |
| `2026-11-06-pipeline-completo-secop-medellin-2025` (con capa limpia) | 13, más 1 para reprobar las hipótesis | ≈ 1,88 millones | 85 min | Ver el informe final de la corrida |

**Lo que funcionó a la primera:**
- El lector aplicó solo las lecciones: cortó el año con `< 2026-01-01` (L02), trajo 6 columnas sin ninguna personal y dejó escritas en «sin verificar» las decisiones de negocio L05, L06 y L07.
- La carga dio 49.662 contratos, igual al conteo del servidor.
- Las implementaciones A y B dieron lo mismo.
- La limpieza marcó, sin borrar filas, 912 atípicos, 609 valores cero o simbólicos y 26 contratos de más de 100.000 millones.

**Lo que encontró el revisor ciego de seguridad** (11 hallazgos en la primera corrida y 8 en la segunda, todos con su prueba):
- **El más grave:** las reglas que escribe la IA se cargaban dentro del verificador, sin compuertas ni caja de arena.
- **Los demás:**
  - CSV leídos sin FAILFAST;
  - mensajes de error con texto de las celdas;
  - `pd.read_csv` con URL;
  - enlaces externos y HTML de Plotly en el informe y el gráfico;
  - caracteres bidireccionales pegados en el código (*Trojan Source*);
  - código que deduce rutas y lee archivos que nadie le pasó.

Todo quedó corregido, comprobado con las pruebas del propio revisor y convertido en lecciones (L15–L24) y en casos de la batería. El sistema aprende de sus fallas: las compuertas que hoy bloquean la mitad de esos patrones no existían en la mañana.

**Costo:** una corrida completa cuesta entre 1,5 y 1,9 millones de tokens. Por eso los participantes no corren el flujo para aportar (ver `CONTRIBUTING.md`).

La compuerta de seguridad tiene su propia evidencia: [`compuerta/README.md`](compuerta/README.md).

## Qué se concluye, sin adornos

1. **Con acceso a los datos y un glosario claro, el modelo de un solo disparo acertó 6 de 6** (contando la decisión declarada sobre la universidad privada) y avisó bien. La intuición de que los modelos actuales son confiables se sostiene en estas pruebas.
2. **El sistema no corrigió ninguna cifra en estas corridas:** sus generadores también acertaron. Aporta otra cosa:
   - evidencia que no depende de creerle al modelo (un criterio sellado y probado con mutantes);
   - errores atrapados cuando sí ocurren (el de `dayfirst`);
   - las preguntas de negocio convertidas en decisiones explícitas;
   - compuertas de datos personales y de seguridad.
3. **Cuesta entre 3,4 y 4,5 veces los tokens de un generador solo** y algo más del doble de tiempo. El control se ajusta al riesgo (directriz D28).

## Cómo reproducirlo

Ver «Validar este repositorio en 15 minutos» en `DIRECTRICES.md`. Para SECOP, primero se descarga el recorte con el contrato de datos de la corrida (`herramientas/ingesta.py`), con el filtro del 1-jul-2024 al 30-jun-2026, en `ejemplo-secop/datos/`. Como SECOP cambia a diario, las cifras pueden variar un poco y los sellos de las corridas de SECOP no se verifican con datos de otro día. Luego:

```bash
ls evidencia/secop/mutantes/*.py | sed 's#.*/\(.*\)\.py#\1=&#' | \
  xargs .venv/bin/python herramientas/verificar.py corridas/2026-11-06-secop-medellin-2025 --impl
```

`--impl` deja `informe_extra.json` dentro de la corrida; se puede borrar después.
