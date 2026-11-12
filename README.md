# Subagentes para procesamiento de big data: la IA propone, una prueba sin IA comprueba

Un análisis de datos hecho con IA, de la pregunta al informe, en las cinco etapas del ciclo del dato. En cada etapa la IA hace el trabajo y una prueba que no es IA lo comprueba. Quien pide el análisis no lee código: lee un informe de una página con la cifra, lo que se entendió, los supuestos, las preguntas abiertas y qué pasó cada prueba.

Quién analiza: las personas, en las dos herramientas. En el pipeline de esta versión, la IA ya no propone ni prueba hipótesis: el documentador resume lo desarrollado en un whitepaper sin conclusiones, una prueba sin IA lo comprueba y las personas escriben su hipótesis antes de mirar (`plantillas/analisis_humano.md`). En el [agente masivo](#agente-masivo-de-datos-públicos) y en su whitepaper, igual: la IA deja preguntas y un resumen, sin conclusiones.

Material aplicado del curso **«Big Data con IA»** (NODO · Universidad EAFIT, noviembre de 2026). Sirve para cualquier fuente pública de datos masivos o para un archivo propio: **ningún subagente trae un conjunto de datos por defecto.** La fuente se declara en cada corrida (`fuente` o `datos`), y al agente masivo se le puede sugerir de qué se va a tratar (`--tema`). Las corridas de ejemplo se midieron con SECOP II (contratos públicos de datos.gov.co) y con ventas sintéticas.

## Grill-me con su IA: el harness y el pipeline

Los dos grill-me del curso se hacen con la IA que ya usa cada persona, desde este repositorio. Cópiele uno de estos textos:

```text
Conéctate al repositorio https://github.com/CristianBTA/subagentes-big-data y sigue su guía GENERAR-HARNESS.md. Quiero generar el harness.
```

```text
Conéctate al repositorio https://github.com/CristianBTA/subagentes-big-data y sigue su guía GRILL-ME-DEL-PIPELINE.md. Quiero hacer el grill-me del pipeline.
```

La IA hace las preguntas una a la vez, repregunta cuando la respuesta queda vaga y, al final, hace el *fork* y guarda el resultado en el fork de la persona (`harness/<usuario>.md` o `grill-me/<usuario>.md`). No gasta tokens del curso y no hace falta *pull request*: el dueño recoge los archivos de los forks con `herramientas/recoger_grill.py`.

**Para la IA que llega aquí:** si la persona dice «Quiero generar el harness», sigue [`GENERAR-HARNESS.md`](GENERAR-HARNESS.md) (enlace directo: https://raw.githubusercontent.com/CristianBTA/subagentes-big-data/main/GENERAR-HARNESS.md). Si dice «Quiero hacer el grill-me del pipeline», sigue [`GRILL-ME-DEL-PIPELINE.md`](GRILL-ME-DEL-PIPELINE.md) (https://raw.githubusercontent.com/CristianBTA/subagentes-big-data/main/GRILL-ME-DEL-PIPELINE.md). Primero las preguntas; el fork, al final.

## Versión para la clase y versión final

- **Para la clase** (6 y 7 de noviembre de 2026) se usa la etiqueta fija **`clase-2026-11-06`**: una versión probada que no cambia aunque `main` siga avanzando.
  ```bash
  git clone --branch clase-2026-11-06 https://github.com/CristianBTA/subagentes-big-data
  ```
  La etiqueta se rehízo una sola vez: el 6 de noviembre a las 15:50 pasó de `7d2fa19` a `42576ec`. Si la descargaste antes, `git pull` no la actualiza: vuelve a clonar, o corre `git fetch --tags --force` y después `git checkout clase-2026-11-06`. Otra versión para la clase llevaría una etiqueta nueva.
- **La versión final está en `main`** ([v1.8](CHANGELOG.md)). Junta los arreglos de la revisión ciega de analista senior y de la revisión del pipeline, el filtro de aportes que toma su juez de la rama base y el cambio por el que el análisis lo hacen las personas: la IA documenta lo desarrollado en un whitepaper, que también sale en tres hojas carta, y la presentación dice lo medido, sin recomendar ni pedir decisiones. Hoy tiene 11 subagentes, 10 baterías, 39 pruebas de blindaje (B00 de control y 38 ataques) y 125 lecciones. La etiqueta `clase-2026-11-06` no se mueve: sigue en la versión de la clase.
- **Los aportes de los participantes** van siempre contra `main`, como dice [`APORTAR-CON-TU-AGENTE.md`](APORTAR-CON-TU-AGENTE.md).

## Conectar la IA

Para aportar con la IA que ya usas (ChatGPT, Gemini, Claude, Copilot u otra), cópiale este texto:

```text
Lee https://raw.githubusercontent.com/CristianBTA/subagentes-big-data/main/APORTAR-CON-TU-AGENTE.md, sigue sus «Instrucciones para el agente» y empieza mi aporte al repositorio CristianBTA/subagentes-big-data.
```

- **La IA te pregunta tu idea y arma el aporte.** Si trabaja con archivos y terminal (Claude Code, Codex, Copilot en VS Code, Cursor), deja listo el *pull request*. Si es un chat, te entrega el texto para el formulario [«Proponer un aporte»](https://github.com/CristianBTA/subagentes-big-data/issues/new?template=aporte.yml).
- **No gasta tu cuota más allá de esa conversación:** el filtro del repositorio no usa IA, y la prueba con IA la paga el dueño.
- Si tu IA no puede abrir enlaces, pégale el archivo [`APORTAR-CON-TU-AGENTE.md`](APORTAR-CON-TU-AGENTE.md) completo.

| Etapa | La IA… | La prueba sin IA |
|---|---|---|
| **Ingesta** | escribe el lector: un contrato de datos con fuente, columnas, tipos, llave, dominios y rangos | conteo contra la fuente, llave única y sin nulos, tipos, rangos, dominios, minimización, correr dos veces da el mismo archivo, procedencia con fecha y huella |
| **Procesamiento** | limpia y transforma: especificación, plan de limpieza, reglas, caso con respuesta conocida y dos implementaciones independientes | capa limpia con las mismas filas y marcas de calidad, calidad antes y después con umbrales, criterio sellado antes del código, reglas sobre el dato crudo, caso conocido, A = B, conciliación, repetibilidad, compuertas y caja de arena |
| **Análisis** | no da el análisis, que lo hacen las personas: solo resume lo desarrollado en un whitepaper, con preguntas de costo, calidad e impacto | cada cifra del whitepaper está en los artefactos verificados, sin conclusiones ni recomendaciones, con sus secciones y sus preguntas (`validar_whitepaper.py`); las personas escriben su hipótesis antes de mirar (`plantillas/analisis_humano.md`) |
| **Visualización** | genera el gráfico y propone la presentación (solo textos y cifras declaradas) | cuenta de control, eje desde cero, título con período, unidades, fuente y fecha, color con contraste y apto para daltonismo, un solo eje, sin datos personales; en la presentación: lo preguntado y lo medido primero, títulos que dicen lo medido, preguntas para las personas y cada cifra calculada y escrita por el código |
| **Gobernanza** | halla datos personales con nombres, tipos y conteos, nunca filas | barrido determinista de datos y salidas, k-anonimato, comparación con la IA, revisión ciega de seguridad y baterías |

- **Los subagentes y sus parámetros:** [`agentes/`](agentes/README.md). Once fichas independientes de la herramienta (rol, qué puede leer y qué no, qué entrega, reglas, lo que nunca hace y la prueba sin IA que lo comprueba), las reglas comunes y la matriz de quién puede ver qué.
- **Cómo validar el trabajo y qué exige cada práctica:** [`DIRECTRICES.md`](DIRECTRICES.md), con la guía «Validar este repositorio en 15 minutos».
- **La seguridad como sistema (SGSI):** [`sgsi/`](sgsi/README.md). Inventario con su valor en confidencialidad, integridad y disponibilidad, 27 riesgos, la Declaración de Aplicabilidad de los 93 controles de ISO/IEC 27001:2022 y la regla de la tríada (la confidencialidad no tiene reversa, la integridad se corrige, la disponibilidad se restablece), comprobados sin IA por `herramientas/sgsi.py`. Las vulnerabilidades se reportan en privado: [`SECURITY.md`](SECURITY.md).
- **Qué se midió:** [`evidencia/README.md`](evidencia/README.md). Generadores de un solo disparo frente al sistema verificado, en datos sintéticos y en SECOP II, con la prueba del criterio por mutantes (12 de 12 y 11 de 11) y los costos.

## Aportar

Cualquiera con cuenta de GitHub puede hacer [fork](https://github.com/CristianBTA/subagentes-big-data/fork) y proponer una lección, un caso de prueba o una regla, sin invitación y **sin gastar su cuota de IA**. El flujo `abierta-a-aportes` comprueba cada día que el repositorio siga abierto: público, con fork y pull requests para cualquiera, y con el formulario y el instructivo publicados. Todo pasa por un embudo antes de entrar:

1. un filtro automático sin IA (`validar-aporte`): datos personales, seguridad del código y que no rompa nada;
2. la revisión del dueño;
3. solo para las reglas de los subagentes, una prueba con IA que paga la licencia del dueño.

`main` está protegida. **La forma más fácil:** el texto de [«Conectar la IA»](#conectar-la-ia), en la IA que ya usas. Ella lee [`APORTAR-CON-TU-AGENTE.md`](APORTAR-CON-TU-AGENTE.md), te pregunta tu idea, arma el aporte y deja listo el pull request o el texto del formulario. Detalles en [`CONTRIBUTING.md`](CONTRIBUTING.md) y aportes aceptados en [`CHANGELOG.md`](CHANGELOG.md).


## Agente masivo de datos públicos

Recorre un catálogo completo de datos abiertos (datos.gov.co tiene 8.470 conjuntos), mide sin IA qué conjuntos son big data de verdad y cuáles permiten decir «esta unidad está así, aquí, y tiene tal impacto» (un contrato, un caso de salud, un trámite). A los mejores les pide a la IA una **ficha de oportunidad** (preguntas de costo, calidad e impacto para que las personas analicen) y la valida sin IA contra la fuente real:

```bash
.venv/bin/python herramientas/agente_masivo.py www.datos.gov.co --trabajo fuentes/fichas/mi-corrida --descubrir --tema "salud"   # sugiere conjuntos de ese tema; no se conecta a ninguno
.venv/bin/python herramientas/agente_masivo.py www.datos.gov.co --trabajo fuentes/fichas/mi-corrida --conjuntos <los que autorizas> --motor claude   # o agy, codex, ninguno
```

Cómo invocarlo desde la terminal, con agy o con cualquier IA de terminal, y el texto listo para pegar: [`AGENTE-MASIVO.md`](AGENTE-MASIVO.md).

Al final arma, sin IA, un **whitepaper de tres hojas tamaño carta** con el resumen para que el estudiante haga el análisis (`WHITEPAPER.pdf`).

El validador (`herramientas/validar_ficha.py`, V1 a V16) mide la forma: columnas, consultas reales, cruces medidos, grano, sumas creíbles, lugar, k-anonimato y normas verificadas. **Que una ficha pase no la hace publicable:** el juicio de valor lo hacen un juez ciego y las personas.

## Instalar

```bash
python3.13 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements.txt
.venv/bin/python herramientas/baterias.py      # debe dar todas las baterías en ✓ (hoy 10)
.venv/bin/python herramientas/blindaje.py      # cada ataque al pipeline debe salir en RESISTE (hoy 39 pruebas, con el control B00)
```

En macOS, usa el Python 3.13 de Homebrew o, si es el del instalador de python.org, corre antes una vez «Install Certificates.command» (en la carpeta de Python 3.13, dentro de Aplicaciones): ese Python no trae los certificados raíz, y la ingesta, el agente masivo y la vigilancia de dependencias se detienen con «certificado no verificado» en vez de consultar datos.gov.co.

Las herramientas de `herramientas/` son Python sin IA y se pueden correr solas. La orquestación de agentes (`flujo.js`) se ejecuta como flujo de trabajo de Claude Code (herramienta *Workflow*) con estos argumentos; `raiz`, la ruta de tu clon, es obligatoria (sin ella el flujo se detiene antes de llamar a ningún agente):

```json
{
  "peticion": "Valor contratado en 2025 por cada entidad pública con sede en Medellín, según SECOP II. Para cada entidad: nit_entidad, entidad (nombre), valor_contratado y numero_contratos.",
  "corrida": "<ruta del clon>/corridas/AAAA-MM-DD-nombre",
  "glosario": "<ruta del clon>/ejemplo-secop/negocio.md",
  "fuente": {"tipo": "socrata", "dominio": "www.datos.gov.co", "conjunto": "jbjy-vk9h", "titulo": "SECOP II - Contratos Electrónicos",
             "licencia": "CC BY-SA 4.0", "atribucion": "Agencia Nacional de Contratación Pública – Colombia Compra Eficiente", "unidad": "contratos"},
  "raiz": "<ruta del clon>"
}
```

Es la corrida de ejemplo, medida con SECOP II. Con otra fuente cambian la petición, el glosario (o ninguno: lo que no se sabe va como pregunta) y `fuente`, que es obligatoria: sin `fuente` ni `datos`, el flujo no arranca. Con archivos locales, `datos` reemplaza a `fuente`: `{"ventas": "<ruta>/ventas.csv", "clientes": "<ruta>/clientes.csv"}`.

### Con agy o con Codex

`orquestar.mjs` corre el mismo `flujo.js`, sin copiarlo ni reescribirlo. Cada subagente es una llamada no interactiva de la CLI, en un contexto nuevo. Los argumentos van en un archivo JSON, los mismos de arriba; aquí `raiz` es opcional: `orquestar.mjs` pone la carpeta donde está.

```bash
node orquestar.mjs --motor agy   --args corrida.json      # agy -p (Gemini por defecto)
node orquestar.mjs --motor codex --args corrida.json      # codex exec
node orquestar.mjs --motor codex --args corrida.json --simulacro   # sin IA: muestra cada llamada y recorre el flujo
node orquestar.mjs --motor agy --comprobar                        # dos llamadas mínimas antes de una corrida completa
```

- **Requisitos:** Node 18 o más, la CLI con sesión iniciada (`agy`, o `codex login`) y el `.venv` de [Instalar](#instalar).
- **Respuestas estructuradas:** cada subagente termina con un JSON que el orquestador valida contra el esquema de `flujo.js`. Si no viene, le pide una sola vez que lo devuelva. Una respuesta vacía, bloqueada o fuera del esquema no cuenta como aprobada: el flujo se detiene como en Claude Code.
- **Modelos:** `--modelo` para los subagentes y `--modelo-ligero` para los que solo corren un comando. En agy el ligero es `gemini-3.8-flash-low`; en Codex es el modelo de la cuenta con esfuerzo bajo. En agy, si el filtro de Gemini bloquea una respuesta, se repite con `--modelo-respaldo` (`gpt-oss-120b-medium`).
- **Sin servidores MCP:** cada llamada los apaga (agy, con un HOME temporal que enlaza `~/.gemini` salvo `mcp_config.json`; Codex, con `-c mcp_servers.<nombre>.enabled=false`), para que ninguno se conecte al navegador del usuario. `--con-mcp` los deja encendidos.
- **Permisos:** agy corre con `--dangerously-skip-permissions` y Codex con `--dangerously-bypass-approvals-and-sandbox`. La ingesta necesita red y la caja de arena de las herramientas (`sandbox-exec`, `caja.py`) no se abre dentro de otra. El código que escribe la IA sigue corriendo en `caja.py`, sin red ni escritura.
- **Registro:** el prompt, la salida y el resultado de cada subagente quedan en `<corrida>/motor/`, que no se sube a git. `--tope-min` limita cada subagente (60 minutos por defecto).

## Herramientas (sin IA)

| Archivo | Qué hace |
|---|---|
| `herramientas/ingesta.py` | Ejecuta el contrato de datos contra datos.gov.co (Socrata) o un CSV local, con las pruebas de carga y la procedencia |
| `herramientas/limpieza.py` | Ejecuta el plan de limpieza: capa limpia con marcas `calidad_*`, sin borrar filas, con calidad antes y después y umbrales |
| `herramientas/perfilar.py` | Perfil determinista: formatos, fechas ambiguas y con hora, repetidos, variantes, códigos que no cruzan y códigos con varios nombres; lee con el lector estricto común (un CSV mal formado lo detiene con su línea) y nunca muestra valores personales, de texto libre ni sensibles |
| `herramientas/verificar.py` | Compuertas, caja de arena, reglas, caso conocido, A = B, conciliación, repetibilidad, tiempos y anticipo; `<corrida> --autoprueba` (solo el caso conocido: no necesita los datos de SECOP) y `<corrida> --sellar` |
| `herramientas/verificar_hipotesis.py` | Sella las hipótesis y las prueba contra su umbral y su línea base, con `hipotesis.py` en la caja aislada (sin leer el umbral sellado); desde el 6-nov la usan las personas, no la IA, en la carpeta que arma `--preparar` (solo el `spec.json` de la corrida y la plantilla, sin las hipótesis de la IA ni datos) |
| `herramientas/validar_whitepaper.py` | Valida el whitepaper del documentador: secciones, cada cifra en los artefactos verificados, sin conclusiones ni recomendaciones, preguntas de costo, calidad e impacto y sin texto oculto; `--autoprueba` |
| `herramientas/whitepaper_corrida.py`, `carta.py` | Maqueta el whitepaper validado en tres hojas carta (`WHITEPAPER.pdf` y `WHITEPAPER.html`) sin cambiar una palabra, solo si su huella es la validada y sin enlaces en el PDF; `carta.py` es el armador común con `whitepaper_fichas.py` |
| `herramientas/verificar_grafico.py` | Lista de comprobación del gráfico, con color y forma (`color.py`: contraste WCAG y simulación de daltonismo) y sin lenguaje de análisis en ningún texto (D15), con `grafico.py` en la caja aislada; escribe el HTML |
| `herramientas/verificar_presentacion.py` | Calcula y escribe cada cifra de la presentación desde los datos aprobados (la IA solo pone marcadores), comprueba su estructura y escribe las láminas si todo aprueba; `--autoprueba` con mutantes |
| `herramientas/gobernanza.py` | Datos personales e instrucciones en los datos y en todas las salidas (informe, resultado, gráfico, whitepaper y presentación), k-anonimato y comparación con la clasificación de la IA |
| `herramientas/seguridad.py`, `dependencias.py`, `caja.py` | Análisis estático (reglas propias y Bandit), librerías permitidas y caja de arena |
| `herramientas/seguridad_cwe.py`, `medir_compuerta.py` | Reglas por debilidad (11 CWE) y dos perfiles: función pura y código de usuario; medida de la compuerta con un lote sellado |
| `herramientas/comprobar.py`, `gancho_compuerta.py`, `medir_real.py` | La compuerta como un solo comando (`.py` y `.ipynb`), su conexión con Claude Code y la medida con código generado de verdad y jurado a ciegas |
| `herramientas/baterias.py` | Baterías de seguridad, privacidad, FAILFAST, inyección, cruces, fechas, repetidos, factor de expansión, gráfico y lecciones; `--agregar-malo` y `--leccion` para que lo que falló no se repita |
| `herramientas/validar_aporte.py`, `rutas_protegidas.py` | Filtro automático de aportes, sin IA: archivos prohibidos, datos personales y órdenes a los agentes en todo lo que agrega, leído por su contenido (también PDF y metadatos de imágenes), seguridad y que no rompa nada; y las rutas que solo cambia el dueño (el filtro, lo que importa, la compuerta y los flujos y ganchos de git) |
| `herramientas/blindaje.py`, `mutar_controles.py` | Banco de ataques al pipeline: caja de arena, compuerta, perfil, salidas, integridad, dependencias, generalización, baterías, filtro de aportes y fichas (con control positivo, B00); `mutar_controles.py` quita cada control en una copia y exige que su prueba del banco ceda |
| `herramientas/integridad.py` | Manifiesto de integridad: sella herramientas, fichas y baterías al inicio y lo comprueba al final |
| `herramientas/informe_final.py` | Informe de las cinco etapas en Markdown y HTML, con todo el texto escapado |
| `herramientas/sgsi.py` | SGSI sin IA: inventario C·I·D, riesgos con la regla de la tríada, Declaración de Aplicabilidad, etiqueta C·I·D de cada corrida; `--efectividad` y `--autoprueba` |
| `herramientas/vulnerabilidades.py` | Vulnerabilidades conocidas (OSV) en las dependencias fijadas de `requirements.txt`, sin llaves |

## Estructura

```
flujo.js                 orquestación de las cinco etapas (historial/ guarda la versión 1)
orquestar.mjs            corre flujo.js con agy o con Codex (un subagente = una llamada de la CLI)
herramientas/            pruebas y utilidades sin IA
baterias/                seguridad, privacidad, FAILFAST, inyección, cruces, fechas, repetidos, factor, gráfico y lecciones: lo que falló una vez, probado siempre
ejemplo/                 ventas sintéticas con trampas conocidas y su glosario
agentes/                 parámetros de los once subagentes, reglas comunes y quién puede ver qué
ejemplo-secop/           glosario de SECOP II (los datos no se publican: se descargan con ingesta.py)
corridas/<fecha-nombre>/ spec, reglas, caso conocido, implementaciones, bitácora e informes de cada corrida
evidencia/               experimentos: oráculos, mutantes, código y advertencias de los generadores de un solo disparo
DIRECTRICES.md           directrices de nivel senior y cómo validar este repositorio
sgsi/                    SGSI: activos, riesgos, controles, Declaración de Aplicabilidad e informe generado
SECURITY.md              cómo reportar una vulnerabilidad en privado y cómo se responde según C, I o D
CONTRIBUTING.md          cómo aportar sin gastar cuota, y el embudo de validación
CHANGELOG.md             versiones y aportes aceptados, con crédito
.github/                 filtro automático y vigilancia diaria (GitHub Actions), formulario de aporte, plantilla y dueño de las revisiones
```

## Licencias

- El código está bajo licencia MIT (`LICENSE`).
- Este repositorio **no publica los datos de SECOP II**: se descargan con `herramientas/ingesta.py` y el contrato de datos de cada corrida (`contrato_contratos.json`). Las cifras agregadas que aparecen en los informes vienen de SECOP II - Contratos Electrónicos, de la Agencia Nacional de Contratación Pública – Colombia Compra Eficiente, publicado en datos.gov.co con licencia CC BY-SA 4.0.
- Los datos de `ejemplo/` son sintéticos.
