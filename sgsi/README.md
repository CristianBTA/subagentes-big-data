# SGSI del pipeline: la tríada C·I·D aplicada

Un SGSI (sistema de gestión de seguridad de la información, ISO/IEC 27001:2022) es la forma ordenada de decidir qué proteger, de qué, con qué controles y cómo saber que funcionan. Su objetivo es preservar tres propiedades de la información:

| | Propiedad | Se pierde cuando… | Ley 1581 de 2012, art. 4, lit. g |
|---|---|---|---|
| **C** | Confidencialidad | alguien sin autorización la lee | «consulta, uso o acceso no autorizado o fraudulento» |
| **I** | Integridad | alguien la cambia sin que se note | «adulteración» |
| **D** | Disponibilidad | no está cuando se necesita | «pérdida» |

Aquí se aplica al repositorio con la misma idea de todo lo demás: **el SGSI lo escribe una persona (o una IA) y una prueba sin IA lo comprueba.** Un SGSI en papel puede declarar controles que no existen; este no, porque `herramientas/sgsi.py` revisa que cada control apunte a evidencia real y, con `--efectividad`, que sus pruebas pasen hoy.

- **Lo que se lee:** [`INFORME-SGSI.md`](INFORME-SGSI.md), generado desde los datos: la tríada por activo, el mapa de calor, los riesgos, la Declaración de Aplicabilidad y la etiqueta C·I·D de cada corrida.
- **Los datos:** [`activos.json`](activos.json), [`riesgos.json`](riesgos.json), [`controles.json`](controles.json) y [`soa.json`](soa.json).

```bash
.venv/bin/python herramientas/sgsi.py                  # comprueba (sin red, sin escribir nada)
.venv/bin/python herramientas/sgsi.py --escribir       # además regenera INFORME-SGSI.md
.venv/bin/python herramientas/sgsi.py --efectividad    # además corre las pruebas de cada control (cerca de 1 minuto)
.venv/bin/python herramientas/sgsi.py --efectividad --en-linea   # más las comprobaciones con red
```

## La regla de la tríada

Las tres propiedades no se rompen igual, y por eso no se protegen igual (curso NODO, clase 1):

| | Cuando se rompe… | Qué control hace falta | Qué comprueba `sgsi.py` |
|---|---|---|---|
| **C** | **no tiene reversa:** lo que se filtró ya se copió | **preventivo:** que no salga | un riesgo de C se mitiga con un control preventivo; los detectivos y correctivos se listan, pero **no bajan el riesgo** |
| **I** | **se corrige**, si se detecta | **detectivo:** notar el cambio antes de publicar | un riesgo de I se mitiga con un control detectivo; solo un detectivo baja su impacto |
| **D** | **se restablece** | **correctivo:** volver a tenerlo | un riesgo de D se mitiga con un control correctivo; solo un correctivo baja su impacto |

En las tres, solo un control **preventivo** baja la probabilidad. Si el residual baja sin el tipo de control que corresponde, la herramienta lo rechaza y lo vuelve al inherente.

## Alcance (4.3)

- **Dentro:** este repositorio público, el pipeline (herramientas, fichas de los subagentes, orquestación), sus flujos de GitHub Actions, las corridas publicadas y las copias de datos que el pipeline descarga en el equipo donde corre.
- **Fuera:** las cuentas personales del dueño y de quienes aportan, el equipo del dueño (salvo lo que la caja de arena protege del código de la IA) y los proveedores. Lo que entra y sale de ellos se trata como relación con proveedores.

## Método (6.1.2 y 6.1.3)

1. **Activos** (A.5.9): cada uno con propietario, custodio, clasificación (A.5.12) y valor de 1 a 5 en C, en I y en D, con su porqué. La clasificación sale de la C: pública (1–2), interna (3) y restringida (4–5). Lo restringido nunca entra al repositorio público, y la herramienta lo comprueba contra `git ls-files` y `.gitignore`.
2. **Riesgos:** cada uno sobre una sola propiedad. La probabilidad (1 a 5) es juicio y dice por qué. **El impacto no se escribe:** es el valor del activo en esa propiedad. Nivel = probabilidad × impacto.
3. **Criterio de aceptación:** nivel residual de 10 o menos, el mismo del ejemplo de la clase 4. Por encima, el dueño del riesgo lo trata o lo acepta por escrito (6.1.3 f); mientras no lo haga, queda como aviso «pendiente del dueño».
4. **Cobertura (6.1.2 c 1):** todo activo con 4 o más en una propiedad tiene al menos un riesgo valorado sobre ella. Todo control trata al menos un riesgo (6.1.3 b).
5. **Declaración de Aplicabilidad (6.1.3 d):** los 93 controles del Anexo A, una sola vez cada uno. Lo que aplica lo implementa un control del repositorio; lo que no aplica dice por qué. Las propiedades C·I·D de cada fila salen de los controles que la implementan, no de la tabla de ISO/IEC 27002:2022, que la propia norma presenta como ilustrativa (4.2).
6. **Medición (9.1):** `--efectividad` corre las pruebas de cada control (banco de blindaje, baterías, corrida sintética y mutantes) y solo cuenta los controles que pasan. La vigilancia diaria lo corre sobre `main`.

## Proveedores

| Proveedor | Para qué | Qué recibe | Qué nunca recibe |
|---|---|---|---|
| GitHub | código, aportes y flujos automáticos | el repositorio público | datos de SECOP, llaves, datos de personas |
| datos.gov.co (Socrata) | fuente de SECOP II | consultas con filtro y columnas | nada del repositorio |
| OSV (osv.dev) | vulnerabilidades conocidas | nombre y versión de cada dependencia | código o datos |
| Asistentes de IA (del dueño y de quienes aportan) | escribir especificaciones, planes y código | nombres de columnas, tipos, conteos y el instructivo | filas ni valores de personas (D18) |

## Restablecer

Lo que se cae se restablece; el orden:

1. **El código:** de GitHub o de cualquier clon (git guarda todo en cada copia). `main` no se puede borrar ni reescribir.
2. **Los datos:** SECOP con el contrato de datos de cada corrida (`herramientas/ingesta.py <contrato> --salida <carpeta> --repetir`); los sintéticos con la semilla (`evidencia/sintetico/generar_datos.py`).
3. **La prueba de que quedó bien:** los pasos de «Validar este repositorio en 15 minutos» de [`DIRECTRICES.md`](../DIRECTRICES.md).
4. **Si falla la comprobación diaria `abierta-a-aportes`:** en *Settings → General* del repositorio, revisar que sea público, con *Issues* activos y *pull requests* para cualquiera; y que `main` tenga la plantilla y el instructivo.

## Retención

Los datos crudos y la capa limpia de SECOP (los CSV de `corridas/*/datos/`, `corridas/*/limpio/`, `ejemplo-secop/datos/`) se borran al cerrar la corrida. No se pierde nada: se reconstruyen con el contrato de datos, y la procedencia (`corridas/*/datos/procedencia_<tabla>.json`, que sí se publica: no trae filas) dice con qué consulta exacta, qué versión de la fuente y qué huella. Es una práctica escrita, no un borrado automático (riesgo R27).

## Lo que este SGSI no garantiza

- **No es una certificación.** Es una autoevaluación con el método de la norma, comprobada sin IA.
- La probabilidad es juicio; la herramienta solo exige que diga por qué.
- Algunos controles son documentales (sin prueba automática): el informe lo dice control por control.
- La configuración de GitHub (protección de `main`, doble factor de la cuenta) no se comprueba desde el repositorio.
