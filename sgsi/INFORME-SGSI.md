# SGSI del pipeline · informe generado

> Lo escribe `herramientas/sgsi.py --escribir` desde `sgsi/*.json`: no se edita a mano. Cómo se lee y con qué método, en [`README.md`](README.md).

## Resumen

- **16 activos** valorados en confidencialidad, integridad y disponibilidad.
- **27 riesgos:** 15 superan el criterio de aceptación (nivel > 10) antes de los controles; después, 0.
- **40 controles** del repositorio; 31 tienen prueba automática.
- **Declaración de Aplicabilidad:** 64 de los 93 controles del Anexo A aplican; 29 se excluyen con su justificación.

## La tríada por activo

| Activo | Nombre | Clasificación | C | I | D | Propietario |
|---|---|---|---|---|---|---|
| A01 | Datos crudos de SECOP II descargados | restringida | 4 | 3 | 2 | Dueño del repositorio, como responsable de la copia que trata (la fuente es de Colombia Compra Eficiente) |
| A02 | Capa limpia de SECOP II (limpio/) | restringida | 4 | 4 | 2 | Dueño del repositorio |
| A03 | Datos sintéticos del ejemplo y su oráculo | pública | 1 | 3 | 2 | Dueño del repositorio |
| A04 | Criterio sellado: reglas, caso conocido, hipótesis y sus sellos | interna | 3 | 5 | 3 | Dueño del repositorio (lo escribe el especificador y lo sella el revisor) |
| A05 | Herramientas de verificación sin IA | pública | 1 | 5 | 3 | Dueño del repositorio |
| A06 | Fichas de los subagentes, reglas comunes y orquestación | pública | 1 | 5 | 2 | Dueño del repositorio |
| A07 | Baterías, lecciones y clases de debilidad | pública | 1 | 5 | 3 | Dueño del repositorio |
| A08 | Código que escribe la IA en cada corrida | pública | 1 | 4 | 2 | Dueño del repositorio (lo encarga y lo acepta; la IA es un desarrollador externo, A.8.30) |
| A09 | Salidas publicadas: informes y gráficos de cada corrida | pública | 2 | 5 | 2 | Dueño del repositorio |
| A10 | Procedencia, perfiles y bitácoras de las corridas | pública | 2 | 4 | 2 | Dueño del repositorio |
| A11 | Aportes del grupo (pull requests e issues) | pública | 1 | 4 | 2 | Quien aporta, hasta que el dueño lo acepta |
| A12 | Configuración del repositorio en GitHub | pública | 1 | 5 | 4 | Dueño del repositorio |
| A13 | Credenciales del dueño: cuenta de GitHub, tokens y licencia de IA | restringida | 5 | 5 | 3 | Dueño del repositorio |
| A14 | Entorno de ejecución: Python, dependencias fijadas y caja de arena | pública | 1 | 5 | 3 | Dueño del repositorio |
| A15 | Datos del equipo del dueño: usuario local y rutas | pública | 2 | 1 | 1 | Dueño del repositorio |
| A16 | Este SGSI: inventario, riesgos y Declaración de Aplicabilidad | pública | 1 | 4 | 2 | Dueño del repositorio (dueño de los riesgos) |

## Mapa de calor: antes y después de los controles

Filas: probabilidad (5 arriba). Columnas: impacto, que sale del valor del activo en la propiedad que se pierde. En negrilla, las celdas por encima del criterio de aceptación (10).

**Antes de los controles (inherente)**

|  | I1 | I2 | I3 | I4 | I5 |
|---|---|---|---|---|---|
| **P5** | · | R07 | **·** | **·** | **·** |
| **P4** | · | · | **·** | **·** | **R10** |
| **P3** | · | R23 | R03, R24 | **R01, R02, R06, R17, R26, R27** | **R04, R08, R09, R11, R12, R13, R15, R16** |
| **P2** | · | · | R22 | R18, R21, R25 | R05, R14, R19, R20 |
| **P1** | · | · | · | · | · |

**Después de los controles (residual)**

|  | I1 | I2 | I3 | I4 | I5 |
|---|---|---|---|---|---|
| **P5** | · | R07 | **·** | **·** | **·** |
| **P4** | · | · | **·** | **·** | **·** |
| **P3** | R23 | R10 | · | **·** | **·** |
| **P2** | · | R08, R09, R15, R17, R25 | R03, R16, R27 | · | · |
| **P1** | · | R18, R21, R22, R24 | R01, R02, R06, R11, R12, R13, R14, R26 | R20 | R04, R05, R19 |

## Riesgos

| Riesgo | Pierde | Amenaza | Inherente | Controles (tipo) | Residual | Estado |
|---|---|---|---|---|---|---|
| R01 | confidencialidad | Datos de SECOP II con personas se suben al repositorio público (un «git add .» o un aporte con la carpeta datos/ o limpio/) | 3×4 = 12 | CT02 (prev.), CT01 (prev.), CT19 (prev.), CT31 (prev.); no reducen, porque la C no tiene reversa: CT33 | 1×3 = 3 | dentro del criterio |
| R02 | confidencialidad | Una salida publicada (informe, gráfico o tabla) lleva cédulas, nombres o texto libre de personas | 3×4 = 12 | CT03 (prev.), CT04 (prev.), CT01 (prev.), CT17 (prev.) | 1×3 = 3 | dentro del criterio |
| R03 | confidencialidad | Un generador ve el criterio sellado (reglas o caso conocido) y escribe para pasar la prueba | 3×3 = 9 | CT05 (prev.); no reducen, porque la C no tiene reversa: CT06 | 2×3 = 6 | dentro del criterio |
| R04 | confidencialidad | El código de la IA lee secretos del entorno o archivos de la carpeta personal y los saca | 3×5 = 15 | CT13 (prev.), CT12 (prev.) | 1×5 = 5 | dentro del criterio |
| R05 | confidencialidad | Un token o una llave queda en un commit o en un aporte | 2×5 = 10 | CT29 (prev.), CT02 (prev.), CT30 (prev.); no reducen, porque la C no tiene reversa: CT33 | 1×5 = 5 | dentro del criterio |
| R06 | confidencialidad | Texto libre de SECOP con cédulas o nombres escritos a mano llega al perfil, a la IA o al informe | 3×4 = 12 | CT01 (prev.), CT04 (prev.), CT03 (prev.) | 1×3 = 3 | dentro del criterio |
| R07 | confidencialidad | Archivos versionados guardan rutas absolutas del equipo del dueño | 5×2 = 10 | no reducen, porque la C no tiene reversa: CT39 | 5×2 = 10 | dentro del criterio |
| R08 | integridad | Un agente o un aporte edita una herramienta, una ficha o una batería para que todo apruebe | 3×5 = 15 | CT08 (det.), CT20 (prev.), CT19 (prev.), CT25 (det.), CT37 (det.) | 2×2 = 4 | dentro del criterio |
| R09 | integridad | El criterio o el umbral se cambia después de ver el resultado | 3×5 = 15 | CT07 (det.), CT05 (prev.), CT06 (det.) | 2×2 = 4 | dentro del criterio |
| R10 | integridad | El código de la IA trae un error silencioso (fechas, duplicados, uniones, marcas) y la cifra sale mal | 4×5 = 20 | CT09 (det.), CT10 (det.), CT11 (prev.), CT27 (corr.), CT24 (corr.) | 3×2 = 6 | dentro del criterio |
| R11 | integridad | El código de la IA trae algo peligroso (ejecutar texto, abrir la red, deserializar, instalar paquetes) y corre en el equipo | 3×5 = 15 | CT12 (prev.), CT13 (prev.), CT26 (det.), CT25 (det.) | 1×3 = 3 | dentro del criterio |
| R12 | integridad | Un valor de los datos con forma de instrucción cambia lo que hace la IA (inyección) | 3×5 = 15 | CT16 (prev.), CT17 (prev.), CT04 (prev.), CT25 (det.) | 1×3 = 3 | dentro del criterio |
| R13 | integridad | Un aporte trae órdenes escondidas para los agentes o debilita una defensa | 3×5 = 15 | CT19 (prev.), CT20 (prev.), CT16 (prev.), CT25 (det.), CT08 (det.), CT24 (corr.) | 1×3 = 3 | dentro del criterio |
| R14 | integridad | Un paquete con nombre inventado o alterado entra al entorno (slopsquatting o paquete comprometido) | 2×5 = 10 | CT14 (prev.), CT12 (prev.), CT15 (det.) | 1×3 = 3 | dentro del criterio |
| R15 | integridad | Un gráfico o un informe engaña (eje truncado, período incompleto sin marcar) o ejecuta algo al abrirse | 3×5 = 15 | CT18 (det.), CT17 (prev.), CT28 (det.) | 2×2 = 4 | dentro del criterio |
| R16 | integridad | Una referencia legal o una cifra inventada por la IA llega a una ficha de oportunidad o a un informe (alucinación) | 3×5 = 15 | CT35 (prev.), CT40 (det.) | 2×3 = 6 | dentro del criterio |
| R17 | integridad | El SGSI declara controles que ya no existen o se queda atrás del código | 3×4 = 12 | CT32 (det.), CT19 (prev.), CT37 (det.) | 2×2 = 4 | dentro del criterio |
| R18 | integridad | La procedencia o la bitácora no corresponden a lo que se hizo | 2×4 = 8 | CT23 (det.), CT28 (det.), CT20 (prev.) | 1×2 = 2 | dentro del criterio |
| R19 | integridad | La configuración de GitHub se debilita (protección de main, permisos de los flujos, acciones sin fijar) | 2×5 = 10 | CT30 (prev.), CT14 (prev.), CT20 (prev.), CT21 (det.) | 1×5 = 5 | dentro del criterio |
| R20 | integridad | Roban la sesión o un token del dueño y cambian main o la configuración sin revisión | 2×5 = 10 | CT29 (prev.), CT30 (prev.), CT37 (det.) | 1×4 = 4 | dentro del criterio |
| R21 | disponibilidad | El repositorio deja de recibir aportes en plena clase (fork o pull requests apagados, plantilla o instructivo borrados) | 2×4 = 8 | CT21 (det.), CT22 (corr.), CT20 (prev.) | 1×2 = 2 | dentro del criterio |
| R22 | disponibilidad | Se pierde el repositorio o el equipo del dueño (borrado, daño o secuestro de datos) | 2×3 = 6 | CT22 (corr.), CT20 (prev.) | 1×2 = 2 | dentro del criterio |
| R23 | disponibilidad | datos.gov.co no responde o el conjunto cambia y la cifra no se puede reproducir | 3×2 = 6 | CT22 (corr.) | 3×1 = 3 | dentro del criterio |
| R24 | disponibilidad | El código de la IA agota la memoria o no termina y la corrida se cae | 3×3 = 9 | CT13 (prev.), CT27 (corr.) | 1×2 = 2 | dentro del criterio |
| R25 | disponibilidad | El filtro automático no corre (GitHub Actions caído o sin minutos) y los aportes quedan sin validar | 2×4 = 8 | CT36 (corr.) | 2×2 = 4 | dentro del criterio |
| R26 | confidencialidad | Filas con datos de personas llegan al proveedor del asistente de IA | 3×4 = 12 | CT04 (prev.), CT01 (prev.), CT34 (prev.) | 1×3 = 3 | dentro del criterio |
| R27 | confidencialidad | Los datos crudos con personas se quedan en el disco más tiempo del necesario | 3×4 = 12 | CT38 (prev.), CT01 (prev.) | 2×3 = 6 | dentro del criterio |

prev. = preventivo, det. = detectivo, corr. = correctivo.

## Declaración de Aplicabilidad (ISO/IEC 27001:2022, 6.1.3 d)

### A.5 · Organizacionales (34 de 37 aplican)

| Control | Nombre | ¿Aplica? | Cómo se aplica o por qué no | C·I·D | Riesgos |
|---|---|---|---|---|---|
| A.5.1 | Políticas de seguridad de la información | Sí | CT32 Este SGSI comprobado sin IA: inventario, clasificación, riesgos y Declaración de Aplicabilidad | C·I·D | R17 |
| A.5.2 | Roles y responsabilidades de seguridad de la información | Sí | CT32 Este SGSI comprobado sin IA: inventario, clasificación, riesgos y Declaración de Aplicabilidad | C·I·D | R17 |
| A.5.3 | Segregación de funciones | Sí | CT05 Separación de funciones entre subagentes: quién puede ver qué; CT20 main protegida: revisión del dueño (CODEOWNERS), sin borrado ni force-push y aprobación de flujos de forks | C·I·D | R03, R08, R09, R13, R18, R19, R21, R22 |
| A.5.4 | Responsabilidades de la dirección | Sí | CT32 Este SGSI comprobado sin IA: inventario, clasificación, riesgos y Declaración de Aplicabilidad | C·I·D | R17 |
| A.5.5 | Contacto con las autoridades | Sí | CT33 Reporte privado de vulnerabilidades y respuesta según la propiedad afectada (SECURITY.md) | C·I·D | R01, R05 |
| A.5.6 | Contacto con grupos de interés especial | No | No se mantienen membresías en grupos de interés: las novedades de amenazas se siguen con fuentes abiertas (OSV en A.5.7 y A.8.8) y con las lecciones del curso. | — | — |
| A.5.7 | Inteligencia de amenazas | Sí | CT15 Vigilancia diaria de vulnerabilidades conocidas en las dependencias fijadas (OSV); CT26 Revisión ciega de seguridad con prueba por hallazgo (D25) | C·I·D | R11, R14 |
| A.5.8 | Seguridad de la información en la gestión de proyectos | Sí | CT32 Este SGSI comprobado sin IA: inventario, clasificación, riesgos y Declaración de Aplicabilidad | C·I·D | R17 |
| A.5.9 | Inventario de información y otros activos asociados | Sí | CT32 Este SGSI comprobado sin IA: inventario, clasificación, riesgos y Declaración de Aplicabilidad | C·I·D | R17 |
| A.5.10 | Uso aceptable de la información y otros activos asociados | Sí | CT31 Procedimientos escritos para operar y aportar: directrices, guía de aportes e instructivo | C·I·D | R01 |
| A.5.11 | Devolución de activos | No | No hay activos que devolver: nadie recibe equipos, llaves ni accesos del repositorio; los aportes llegan por fork, sin invitación como colaborador. | — | — |
| A.5.12 | Clasificación de la información | Sí | CT32 Este SGSI comprobado sin IA: inventario, clasificación, riesgos y Declaración de Aplicabilidad | C·I·D | R17 |
| A.5.13 | Etiquetado de la información | Sí | CT32 Este SGSI comprobado sin IA: inventario, clasificación, riesgos y Declaración de Aplicabilidad | C·I·D | R17 |
| A.5.14 | Transferencia de información | Sí | CT02 Datos fuera del repositorio público: .gitignore y archivos prohibidos en el filtro | C | R01, R05 |
| A.5.15 | Control de acceso | Sí | CT05 Separación de funciones entre subagentes: quién puede ver qué; CT30 Acceso mínimo: aportes sin invitación, flujos de GitHub de solo lectura y sin secretos propios | C·I | R03, R05, R09, R19, R20 |
| A.5.16 | Gestión de identidades | Sí | CT30 Acceso mínimo: aportes sin invitación, flujos de GitHub de solo lectura y sin secretos propios | C·I | R05, R19, R20 |
| A.5.17 | Información de autenticación | Sí | CT29 Sin secretos en lo versionado: escaneo propio y protección de envíos de GitHub | C·I | R05, R20 |
| A.5.18 | Derechos de acceso | Sí | CT20 main protegida: revisión del dueño (CODEOWNERS), sin borrado ni force-push y aprobación de flujos de forks; CT30 Acceso mínimo: aportes sin invitación, flujos de GitHub de solo lectura y sin secretos propios | C·I·D | R05, R08, R13, R18, R19, R20, R21, R22 |
| A.5.19 | Seguridad de la información en las relaciones con proveedores | Sí | CT34 Proveedores con su papel y su límite: GitHub, datos.gov.co, OSV y los asistentes de IA | C·I·D | R26 |
| A.5.20 | Seguridad de la información en los acuerdos con proveedores | No | No hay acuerdos negociados con proveedores: se usan los términos estándar de GitHub, datos.gov.co, OSV y los asistentes de IA; el riesgo se trata limitando lo que cada uno recibe (A.5.19, A.5.23). | — | — |
| A.5.21 | Gestión de la seguridad de la información en la cadena de suministro TIC | Sí | CT14 Cadena de suministro fijada: dependencias con huella y acciones fijadas a su commit (DB7) | I | R14, R19 |
| A.5.22 | Seguimiento, revisión y gestión de cambios de los servicios de proveedores | Sí | CT21 Comprobación diaria de que el repositorio sigue abierto a aportes | I·D | R19, R21 |
| A.5.23 | Seguridad de la información en el uso de servicios en la nube | Sí | CT34 Proveedores con su papel y su límite: GitHub, datos.gov.co, OSV y los asistentes de IA | C·I·D | R26 |
| A.5.24 | Planificación y preparación de la gestión de incidentes | Sí | CT33 Reporte privado de vulnerabilidades y respuesta según la propiedad afectada (SECURITY.md) | C·I·D | R01, R05 |
| A.5.25 | Evaluación y decisión sobre eventos de seguridad de la información | Sí | CT33 Reporte privado de vulnerabilidades y respuesta según la propiedad afectada (SECURITY.md) | C·I·D | R01, R05 |
| A.5.26 | Respuesta a incidentes de seguridad de la información | Sí | CT33 Reporte privado de vulnerabilidades y respuesta según la propiedad afectada (SECURITY.md) | C·I·D | R01, R05 |
| A.5.27 | Aprendizaje de los incidentes de seguridad de la información | Sí | CT24 Baterías que solo crecen: cada error real se vuelve lección y prueba (D26) | C·I·D | R10, R13 |
| A.5.28 | Recolección de evidencias | Sí | CT28 Bitácora del copiloto e informe final con todo el texto escapado (D27); CT33 Reporte privado de vulnerabilidades y respuesta según la propiedad afectada (SECURITY.md) | C·I·D | R01, R05, R15, R18 |
| A.5.29 | Seguridad de la información durante una disrupción | Sí | CT22 Restablecer: todo se reconstruye desde GitHub o un clon, el contrato de datos y la semilla; CT36 El filtro también corre en local con el mismo comando: si GitHub Actions no está, el dueño lo corre antes de aprobar | I·D | R21, R22, R23, R25 |
| A.5.30 | Preparación de las TIC para la continuidad del negocio | Sí | CT21 Comprobación diaria de que el repositorio sigue abierto a aportes; CT22 Restablecer: todo se reconstruye desde GitHub o un clon, el contrato de datos y la semilla; CT36 El filtro también corre en local con el mismo comando: si GitHub Actions no está, el dueño lo corre antes de aprobar | I·D | R19, R21, R22, R23, R25 |
| A.5.31 | Requisitos legales, reglamentarios y contractuales | Sí | CT23 Procedencia con fecha y huella, licencia y atribución de la fuente (D6, D19, D20); CT40 Normas citadas comprobadas contra su texto oficial: toda ley o decreto de una ficha debe estar en el registro de normas verificadas (V6) | I | R16, R18 |
| A.5.32 | Derechos de propiedad intelectual | Sí | CT23 Procedencia con fecha y huella, licencia y atribución de la fuente (D6, D19, D20) | I | R18 |
| A.5.33 | Protección de los registros | Sí | CT07 Criterio e hipótesis sellados con SHA-256 antes del código (D8, D15); CT23 Procedencia con fecha y huella, licencia y atribución de la fuente (D6, D19, D20) | I | R09, R18 |
| A.5.34 | Privacidad y protección de datos personales | Sí | CT01 Minimización en el contrato de datos (D7); CT03 Barrido determinista de datos personales en datos y salidas, con k-anonimato (D18); CT04 Nunca filas a la IA: el perfil y el custodio trabajan con nombres, tipos y conteos (D3, D18) | C·I | R01, R02, R06, R12, R26, R27 |
| A.5.35 | Revisión independiente de la seguridad de la información | Sí | CT26 Revisión ciega de seguridad con prueba por hallazgo (D25) | C·I·D | R11 |
| A.5.36 | Cumplimiento de políticas, reglas y normas de seguridad | Sí | CT06 Auditoría de independencia sobre las transcripciones reales (DB9); CT32 Este SGSI comprobado sin IA: inventario, clasificación, riesgos y Declaración de Aplicabilidad | C·I·D | R03, R09, R17 |
| A.5.37 | Procedimientos de operación documentados | Sí | CT31 Procedimientos escritos para operar y aportar: directrices, guía de aportes e instructivo | C·I·D | R01 |

### A.6 · Personas (2 de 8 aplican)

| Control | Nombre | ¿Aplica? | Cómo se aplica o por qué no | C·I·D | Riesgos |
|---|---|---|---|---|---|
| A.6.1 | Selección del personal | No | No hay personal: el repositorio lo opera una persona y el grupo aporta desde sus propias cuentas, sin acceso al repositorio; los aportes se filtran por su contenido (filtro sin IA y revisión del dueño), no por quién los hace. | — | — |
| A.6.2 | Términos y condiciones del empleo | No | No hay personal: el repositorio lo opera una persona y el grupo aporta desde sus propias cuentas, sin acceso al repositorio; los aportes se filtran por su contenido (filtro sin IA y revisión del dueño), no por quién los hace. | — | — |
| A.6.3 | Concienciación, educación y formación en seguridad de la información | Sí | CT31 Procedimientos escritos para operar y aportar: directrices, guía de aportes e instructivo | C·I·D | R01 |
| A.6.4 | Proceso disciplinario | No | No hay personal: el repositorio lo opera una persona y el grupo aporta desde sus propias cuentas, sin acceso al repositorio; los aportes se filtran por su contenido (filtro sin IA y revisión del dueño), no por quién los hace. | — | — |
| A.6.5 | Responsabilidades después de la terminación o el cambio de empleo | No | No hay personal: el repositorio lo opera una persona y el grupo aporta desde sus propias cuentas, sin acceso al repositorio; los aportes se filtran por su contenido (filtro sin IA y revisión del dueño), no por quién los hace. | — | — |
| A.6.6 | Acuerdos de confidencialidad o de no divulgación | No | No se comparte información confidencial con terceros: todo lo que se publica es público a propósito y los datos con personas nunca salen del equipo del dueño (A.8.12). | — | — |
| A.6.7 | Trabajo remoto | No | No hay personal que trabaje a distancia; el único equipo de trabajo es el del dueño, fuera del alcance (ver A.8.1 para lo que la caja de arena protege). | — | — |
| A.6.8 | Reporte de eventos de seguridad de la información | Sí | CT33 Reporte privado de vulnerabilidades y respuesta según la propiedad afectada (SECURITY.md) | C·I·D | R01, R05 |

### A.7 · Físicos (0 de 14 aplican)

| Control | Nombre | ¿Aplica? | Cómo se aplica o por qué no | C·I·D | Riesgos |
|---|---|---|---|---|---|
| A.7.1 | Perímetros de seguridad física | No | Sin instalaciones propias dentro del alcance: el código vive en GitHub (proveedor, A.5.19 y A.5.23) y el pipeline corre en el equipo del dueño, que queda fuera del alcance; la caja de arena protege ese equipo del código de la IA (A.8.1). | — | — |
| A.7.2 | Controles físicos de entrada | No | Sin instalaciones propias dentro del alcance: el código vive en GitHub (proveedor, A.5.19 y A.5.23) y el pipeline corre en el equipo del dueño, que queda fuera del alcance; la caja de arena protege ese equipo del código de la IA (A.8.1). | — | — |
| A.7.3 | Seguridad de oficinas, recintos e instalaciones | No | Sin instalaciones propias dentro del alcance: el código vive en GitHub (proveedor, A.5.19 y A.5.23) y el pipeline corre en el equipo del dueño, que queda fuera del alcance; la caja de arena protege ese equipo del código de la IA (A.8.1). | — | — |
| A.7.4 | Monitoreo de la seguridad física | No | Sin instalaciones propias dentro del alcance: el código vive en GitHub (proveedor, A.5.19 y A.5.23) y el pipeline corre en el equipo del dueño, que queda fuera del alcance; la caja de arena protege ese equipo del código de la IA (A.8.1). | — | — |
| A.7.5 | Protección contra amenazas físicas y ambientales | No | Sin instalaciones propias dentro del alcance: el código vive en GitHub (proveedor, A.5.19 y A.5.23) y el pipeline corre en el equipo del dueño, que queda fuera del alcance; la caja de arena protege ese equipo del código de la IA (A.8.1). | — | — |
| A.7.6 | Trabajo en áreas seguras | No | Sin instalaciones propias dentro del alcance: el código vive en GitHub (proveedor, A.5.19 y A.5.23) y el pipeline corre en el equipo del dueño, que queda fuera del alcance; la caja de arena protege ese equipo del código de la IA (A.8.1). | — | — |
| A.7.7 | Escritorio limpio y pantalla limpia | No | Sin instalaciones propias dentro del alcance: el código vive en GitHub (proveedor, A.5.19 y A.5.23) y el pipeline corre en el equipo del dueño, que queda fuera del alcance; la caja de arena protege ese equipo del código de la IA (A.8.1). | — | — |
| A.7.8 | Ubicación y protección de los equipos | No | Sin instalaciones propias dentro del alcance: el código vive en GitHub (proveedor, A.5.19 y A.5.23) y el pipeline corre en el equipo del dueño, que queda fuera del alcance; la caja de arena protege ese equipo del código de la IA (A.8.1). | — | — |
| A.7.9 | Seguridad de los activos fuera de las instalaciones | No | Sin instalaciones propias dentro del alcance: el código vive en GitHub (proveedor, A.5.19 y A.5.23) y el pipeline corre en el equipo del dueño, que queda fuera del alcance; la caja de arena protege ese equipo del código de la IA (A.8.1). | — | — |
| A.7.10 | Medios de almacenamiento | No | Sin instalaciones propias dentro del alcance: el código vive en GitHub (proveedor, A.5.19 y A.5.23) y el pipeline corre en el equipo del dueño, que queda fuera del alcance; la caja de arena protege ese equipo del código de la IA (A.8.1). | — | — |
| A.7.11 | Servicios de suministro | No | Sin instalaciones propias dentro del alcance: el código vive en GitHub (proveedor, A.5.19 y A.5.23) y el pipeline corre en el equipo del dueño, que queda fuera del alcance; la caja de arena protege ese equipo del código de la IA (A.8.1). | — | — |
| A.7.12 | Seguridad del cableado | No | Sin instalaciones propias dentro del alcance: el código vive en GitHub (proveedor, A.5.19 y A.5.23) y el pipeline corre en el equipo del dueño, que queda fuera del alcance; la caja de arena protege ese equipo del código de la IA (A.8.1). | — | — |
| A.7.13 | Mantenimiento de los equipos | No | Sin instalaciones propias dentro del alcance: el código vive en GitHub (proveedor, A.5.19 y A.5.23) y el pipeline corre en el equipo del dueño, que queda fuera del alcance; la caja de arena protege ese equipo del código de la IA (A.8.1). | — | — |
| A.7.14 | Eliminación o reutilización segura de los equipos | No | Sin instalaciones propias dentro del alcance: el código vive en GitHub (proveedor, A.5.19 y A.5.23) y el pipeline corre en el equipo del dueño, que queda fuera del alcance; la caja de arena protege ese equipo del código de la IA (A.8.1). | — | — |

### A.8 · Tecnológicos (28 de 34 aplican)

| Control | Nombre | ¿Aplica? | Cómo se aplica o por qué no | C·I·D | Riesgos |
|---|---|---|---|---|---|
| A.8.1 | Dispositivos de punto final del usuario | Sí | CT13 Caja de arena: sin red, sin escritura, sin la carpeta personal, entorno mínimo y topes de tiempo y memoria (D23, DB2) | C·I·D | R04, R11, R24 |
| A.8.2 | Derechos de acceso privilegiado | Sí | CT30 Acceso mínimo: aportes sin invitación, flujos de GitHub de solo lectura y sin secretos propios | C·I | R05, R19, R20 |
| A.8.3 | Restricción del acceso a la información | Sí | CT04 Nunca filas a la IA: el perfil y el custodio trabajan con nombres, tipos y conteos (D3, D18); CT05 Separación de funciones entre subagentes: quién puede ver qué | C·I | R02, R03, R06, R09, R12, R26 |
| A.8.4 | Acceso al código fuente | Sí | CT19 Filtro automático de aportes, sin IA ni llaves (validar-aporte); CT20 main protegida: revisión del dueño (CODEOWNERS), sin borrado ni force-push y aprobación de flujos de forks | C·I·D | R01, R08, R13, R17, R18, R19, R21, R22 |
| A.8.5 | Autenticación segura | No | El repositorio no autentica a nadie: los aportes llegan por pull request y los revisa el dueño. La autenticación es la de la cuenta de GitHub del dueño, fuera del alcance (riesgo R20 para su robo). | — | — |
| A.8.6 | Gestión de la capacidad | Sí | CT13 Caja de arena: sin red, sin escritura, sin la carpeta personal, entorno mínimo y topes de tiempo y memoria (D23, DB2) | C·I·D | R04, R11, R24 |
| A.8.7 | Protección contra el malware | Sí | CT12 Compuerta estática (reglas propias y Bandit) y lista cerrada de librerías (D21, D22) | C·I·D | R04, R11, R14 |
| A.8.8 | Gestión de las vulnerabilidades técnicas | Sí | CT15 Vigilancia diaria de vulnerabilidades conocidas en las dependencias fijadas (OSV); CT24 Baterías que solo crecen: cada error real se vuelve lección y prueba (D26); CT37 Vigilancia diaria de main: blindaje, baterías, corrida sintética, mutantes y SGSI | C·I·D | R08, R10, R13, R14, R17, R20 |
| A.8.9 | Gestión de la configuración | Sí | CT08 Manifiesto de integridad de herramientas, fichas y baterías durante la corrida (DB3) | I | R08, R13 |
| A.8.10 | Eliminación de la información | Sí | CT38 Retención mínima: los datos crudos se borran al cerrar la corrida y se reconstruyen con el contrato | C | R27 |
| A.8.11 | Enmascaramiento de datos | Sí | CT03 Barrido determinista de datos personales en datos y salidas, con k-anonimato (D18) | C | R02, R06 |
| A.8.12 | Prevención de la fuga de datos | Sí | CT01 Minimización en el contrato de datos (D7); CT02 Datos fuera del repositorio público: .gitignore y archivos prohibidos en el filtro; CT03 Barrido determinista de datos personales en datos y salidas, con k-anonimato (D18); CT29 Sin secretos en lo versionado: escaneo propio y protección de envíos de GitHub; CT39 Conteo de rutas locales del equipo en lo versionado: no puede crecer sin que se note | C·I | R01, R02, R05, R06, R07, R20, R26, R27 |
| A.8.13 | Copias de respaldo de la información | Sí | CT22 Restablecer: todo se reconstruye desde GitHub o un clon, el contrato de datos y la semilla | I·D | R21, R22, R23 |
| A.8.14 | Redundancia de las instalaciones de procesamiento de información | Sí | CT22 Restablecer: todo se reconstruye desde GitHub o un clon, el contrato de datos y la semilla | I·D | R21, R22, R23 |
| A.8.15 | Registro de eventos | Sí | CT06 Auditoría de independencia sobre las transcripciones reales (DB9); CT28 Bitácora del copiloto e informe final con todo el texto escapado (D27) | C·I | R03, R09, R15, R18 |
| A.8.16 | Actividades de monitoreo | Sí | CT06 Auditoría de independencia sobre las transcripciones reales (DB9); CT21 Comprobación diaria de que el repositorio sigue abierto a aportes; CT37 Vigilancia diaria de main: blindaje, baterías, corrida sintética, mutantes y SGSI | C·I·D | R03, R08, R09, R17, R19, R20, R21 |
| A.8.17 | Sincronización de relojes | No | El repositorio no administra relojes: las fechas de procedencia y de las comprobaciones vienen del sistema operativo y de GitHub. | — | — |
| A.8.18 | Uso de programas utilitarios privilegiados | No | El pipeline no usa programas con privilegios: la caja de arena (sandbox-exec) restringe al código de la IA, no lo eleva. | — | — |
| A.8.19 | Instalación de software en sistemas operativos | Sí | CT12 Compuerta estática (reglas propias y Bandit) y lista cerrada de librerías (D21, D22); CT14 Cadena de suministro fijada: dependencias con huella y acciones fijadas a su commit (DB7) | C·I·D | R04, R11, R14, R19 |
| A.8.20 | Seguridad de las redes | No | Sin red propia que administrar: el código de la IA corre sin red (A.8.22) y la ingesta solo consulta datos.gov.co por HTTPS. | — | — |
| A.8.21 | Seguridad de los servicios de red | No | No se prestan ni se contratan servicios de red administrados; las únicas conexiones son consultas HTTPS a servicios públicos (datos.gov.co, OSV, la API de GitHub). | — | — |
| A.8.22 | Segregación de redes | Sí | CT13 Caja de arena: sin red, sin escritura, sin la carpeta personal, entorno mínimo y topes de tiempo y memoria (D23, DB2) | C·I·D | R04, R11, R24 |
| A.8.23 | Filtrado web | No | No hay navegación web dentro del pipeline que filtrar: el código de la IA no tiene red (A.8.22). | — | — |
| A.8.24 | Uso de la criptografía | Sí | CT07 Criterio e hipótesis sellados con SHA-256 antes del código (D8, D15) | I | R09 |
| A.8.25 | Ciclo de vida de desarrollo seguro | Sí | CT19 Filtro automático de aportes, sin IA ni llaves (validar-aporte); CT27 Reparador con tope de dos rondas; lo que quede lo decide una persona | C·I·D | R01, R08, R10, R13, R17, R24 |
| A.8.26 | Requisitos de seguridad de las aplicaciones | Sí | CT11 FAILFAST, perfil y limpieza declarada: lo que no cumple el contrato se detiene, se explica o se marca (D3, D5, DL3–DL6); CT16 Cuarentena de instrucciones: los datos y los aportes son datos, nunca órdenes (DB4); CT17 Salidas que no ejecutan nada al abrirse: HTML escapado y fórmulas neutralizadas (D24, DB5) | C·I | R02, R10, R12, R13, R15 |
| A.8.27 | Arquitectura de sistemas seguros y principios de ingeniería | Sí | CT11 FAILFAST, perfil y limpieza declarada: lo que no cumple el contrato se detiene, se explica o se marca (D3, D5, DL3–DL6); CT16 Cuarentena de instrucciones: los datos y los aportes son datos, nunca órdenes (DB4) | I | R10, R12, R13 |
| A.8.28 | Codificación segura | Sí | CT12 Compuerta estática (reglas propias y Bandit) y lista cerrada de librerías (D21, D22); CT17 Salidas que no ejecutan nada al abrirse: HTML escapado y fórmulas neutralizadas (D24, DB5) | C·I·D | R02, R04, R11, R12, R14, R15 |
| A.8.29 | Pruebas de seguridad en el desarrollo y la aceptación | Sí | CT09 Verificación sin IA del resultado: dos implementaciones, caso conocido, conservación, conciliación y repetibilidad (D9–D13); CT10 Probar al probador con mutantes (D14); CT18 Lista de comprobación del gráfico: eje desde cero, período, fuente y cuenta de control (D17); CT19 Filtro automático de aportes, sin IA ni llaves (validar-aporte); CT25 Banco de blindaje con control positivo, con datos y secretos ficticios en carpetas temporales (DB1, DB10); CT26 Revisión ciega de seguridad con prueba por hallazgo (D25); CT35 Fichas de oportunidad validadas sin IA: consultas reales, cruces medidos y sin cifras inventadas (V1–V8); CT40 Normas citadas comprobadas contra su texto oficial: toda ley o decreto de una ficha debe estar en el registro de normas verificadas (V6) | C·I·D | R01, R08, R10, R11, R12, R13, R15, R16, R17 |
| A.8.30 | Desarrollo contratado externamente | Sí | CT09 Verificación sin IA del resultado: dos implementaciones, caso conocido, conservación, conciliación y repetibilidad (D9–D13); CT12 Compuerta estática (reglas propias y Bandit) y lista cerrada de librerías (D21, D22) | C·I·D | R04, R10, R11, R14 |
| A.8.31 | Separación de los entornos de desarrollo, prueba y producción | Sí | CT13 Caja de arena: sin red, sin escritura, sin la carpeta personal, entorno mínimo y topes de tiempo y memoria (D23, DB2) | C·I·D | R04, R11, R24 |
| A.8.32 | Gestión de cambios | Sí | CT08 Manifiesto de integridad de herramientas, fichas y baterías durante la corrida (DB3); CT19 Filtro automático de aportes, sin IA ni llaves (validar-aporte); CT20 main protegida: revisión del dueño (CODEOWNERS), sin borrado ni force-push y aprobación de flujos de forks | C·I·D | R01, R08, R13, R17, R18, R19, R21, R22 |
| A.8.33 | Información de prueba | Sí | CT25 Banco de blindaje con control positivo, con datos y secretos ficticios en carpetas temporales (DB1, DB10) | C·I·D | R08, R11, R12, R13 |
| A.8.34 | Protección de los sistemas de información durante las pruebas de auditoría | Sí | CT25 Banco de blindaje con control positivo, con datos y secretos ficticios en carpetas temporales (DB1, DB10) | C·I·D | R08, R11, R12, R13 |

## Controles del repositorio

| Control | Nombre | Tipo | Protege | Anexo A | Prueba automática |
|---|---|---|---|---|---|
| CT01 | Minimización en el contrato de datos (D7) | preventivo | C | A.5.34, A.8.12 | bateria:privacidad |
| CT02 | Datos fuera del repositorio público: .gitignore y archivos prohibidos en el filtro | preventivo | C | A.8.12, A.5.14 | sgsi:restringidos |
| CT03 | Barrido determinista de datos personales en datos y salidas, con k-anonimato (D18) | preventivo | C | A.8.11, A.8.12, A.5.34 | bateria:privacidad, B26, B27 |
| CT04 | Nunca filas a la IA: el perfil y el custodio trabajan con nombres, tipos y conteos (D3, D18) | preventivo | C·I | A.8.3, A.5.34 | bateria:privacidad, B04, B32 |
| CT05 | Separación de funciones entre subagentes: quién puede ver qué | preventivo | C·I | A.5.3, A.5.15, A.8.3 | B24, B28, B29 |
| CT06 | Auditoría de independencia sobre las transcripciones reales (DB9) | detectivo | C·I | A.8.15, A.8.16, A.5.36 | autoprueba:auditar_independencia |
| CT07 | Criterio e hipótesis sellados con SHA-256 antes del código (D8, D15) | detectivo | I | A.8.24, A.5.33 | corrida-sintetica, B29 |
| CT08 | Manifiesto de integridad de herramientas, fichas y baterías durante la corrida (DB3) | detectivo | I | A.8.9, A.8.32 | B02 |
| CT09 | Verificación sin IA del resultado: dos implementaciones, caso conocido, conservación, conciliación y repetibilidad (D9–D13) | detectivo | I | A.8.29, A.8.30 | corrida-sintetica, B05, B25, B31 |
| CT10 | Probar al probador con mutantes (D14) | detectivo | I | A.8.29 | mutantes |
| CT11 | FAILFAST, perfil y limpieza declarada: lo que no cumple el contrato se detiene, se explica o se marca (D3, D5, DL3–DL6) | preventivo | I | A.8.26, A.8.27 | bateria:failfast, bateria:cruces, bateria:fechas, bateria:repetidos, bateria:factor, B09, B19, B33, B34, B39 |
| CT12 | Compuerta estática (reglas propias y Bandit) y lista cerrada de librerías (D21, D22) | preventivo | C·I·D | A.8.28, A.8.7, A.8.19, A.8.30 | bateria:seguridad, B15, B28, B30 |
| CT13 | Caja de arena: sin red, sin escritura, sin la carpeta personal, entorno mínimo y topes de tiempo y memoria (D23, DB2) | preventivo | C·I·D | A.8.22, A.8.31, A.8.6, A.8.1 | B00, B01, B10, B11, B12, B13, B14, B23, B24, B29 |
| CT14 | Cadena de suministro fijada: dependencias con huella y acciones fijadas a su commit (DB7) | preventivo | I | A.5.21, A.8.19 | B08, sgsi:permisos |
| CT15 | Vigilancia diaria de vulnerabilidades conocidas en las dependencias fijadas (OSV) | detectivo | C·I·D | A.8.8, A.5.7 | red:vulnerabilidades |
| CT16 | Cuarentena de instrucciones: los datos y los aportes son datos, nunca órdenes (DB4) | preventivo | I | A.8.26, A.8.27 | bateria:inyeccion, B04, B07 |
| CT17 | Salidas que no ejecutan nada al abrirse: HTML escapado y fórmulas neutralizadas (D24, DB5) | preventivo | C·I | A.8.28, A.8.26 | B03, B17, B18 |
| CT18 | Lista de comprobación del gráfico: eje desde cero, período, fuente y cuenta de control (D17) | detectivo | I | A.8.29 | B17, bateria:grafico |
| CT19 | Filtro automático de aportes, sin IA ni llaves (validar-aporte) | preventivo | C·I | A.8.32, A.8.29, A.8.4, A.8.25 | B07, B20, B21, B22, B35, B36, B40 |
| CT20 | main protegida: revisión del dueño (CODEOWNERS), sin borrado ni force-push y aprobación de flujos de forks | preventivo | I·D | A.8.4, A.8.32, A.5.3, A.5.18 | evidencia documental |
| CT21 | Comprobación diaria de que el repositorio sigue abierto a aportes | detectivo | I·D | A.8.16, A.5.30, A.5.22 | red:abierta_a_aportes |
| CT22 | Restablecer: todo se reconstruye desde GitHub o un clon, el contrato de datos y la semilla | correctivo | I·D | A.8.13, A.8.14, A.5.29, A.5.30 | corrida-sintetica |
| CT23 | Procedencia con fecha y huella, licencia y atribución de la fuente (D6, D19, D20) | detectivo | I | A.5.33, A.5.32, A.5.31 | evidencia documental |
| CT24 | Baterías que solo crecen: cada error real se vuelve lección y prueba (D26) | correctivo | C·I·D | A.5.27, A.8.8 | bateria:lecciones, B37 |
| CT25 | Banco de blindaje con control positivo, con datos y secretos ficticios en carpetas temporales (DB1, DB10) | detectivo | C·I·D | A.8.29, A.8.34, A.8.33 | B00, B38 |
| CT26 | Revisión ciega de seguridad con prueba por hallazgo (D25) | detectivo | C·I·D | A.5.35, A.8.29, A.5.7 | bateria:seguridad |
| CT27 | Reparador con tope de dos rondas; lo que quede lo decide una persona | correctivo | I·D | A.8.25 | evidencia documental |
| CT28 | Bitácora del copiloto e informe final con todo el texto escapado (D27) | detectivo | I | A.8.15, A.5.28 | B18 |
| CT29 | Sin secretos en lo versionado: escaneo propio y protección de envíos de GitHub | preventivo | C·I | A.5.17, A.8.12 | sgsi:secretos |
| CT30 | Acceso mínimo: aportes sin invitación, flujos de GitHub de solo lectura y sin secretos propios | preventivo | C·I | A.5.15, A.5.16, A.5.18, A.8.2 | sgsi:permisos |
| CT31 | Procedimientos escritos para operar y aportar: directrices, guía de aportes e instructivo | preventivo | C·I·D | A.5.37, A.6.3, A.5.10 | evidencia documental |
| CT32 | Este SGSI comprobado sin IA: inventario, clasificación, riesgos y Declaración de Aplicabilidad | detectivo | C·I·D | A.5.1, A.5.2, A.5.4, A.5.8, A.5.9, A.5.12, A.5.13, A.5.36 | sgsi:inventario |
| CT33 | Reporte privado de vulnerabilidades y respuesta según la propiedad afectada (SECURITY.md) | correctivo | C·I·D | A.5.24, A.5.25, A.5.26, A.5.28, A.6.8, A.5.5 | evidencia documental |
| CT34 | Proveedores con su papel y su límite: GitHub, datos.gov.co, OSV y los asistentes de IA | preventivo | C·I·D | A.5.19, A.5.23 | evidencia documental |
| CT35 | Fichas de oportunidad validadas sin IA: consultas reales, cruces medidos y sin cifras inventadas (V1–V8) | preventivo | I | A.8.29 | autoprueba:validar_ficha |
| CT36 | El filtro también corre en local con el mismo comando: si GitHub Actions no está, el dueño lo corre antes de aprobar | correctivo | D | A.5.29, A.5.30 | evidencia documental |
| CT37 | Vigilancia diaria de main: blindaje, baterías, corrida sintética, mutantes y SGSI | detectivo | C·I·D | A.8.16, A.8.8 | evidencia documental |
| CT38 | Retención mínima: los datos crudos se borran al cerrar la corrida y se reconstruyen con el contrato | preventivo | C | A.8.10 | evidencia documental |
| CT39 | Conteo de rutas locales del equipo en lo versionado: no puede crecer sin que se note | detectivo | C | A.8.12 | sgsi:secretos |
| CT40 | Normas citadas comprobadas contra su texto oficial: toda ley o decreto de una ficha debe estar en el registro de normas verificadas (V6) | detectivo | I | A.5.31, A.8.29 | autoprueba:validar_ficha |

## Etiqueta C·I·D de las corridas publicadas

| Corrida | C · sus salidas | I · su resultado | D · si se pierde |
|---|---|---|---|
| 2026-11-06-pipeline-completo-secop-medellin-2025 | publicable: barrido de datos personales limpio; solo agregados, sin columnas de personas | íntegra: huellas del criterio recalculadas al generar este informe y resultado aprobado sin IA | reconstruible: se vuelve a descargar con el contrato de datos (ingesta.py) y se compara con la procedencia |
| 2026-11-06-pipeline-secop-medellin-2025 | publicable: barrido de datos personales limpio; solo agregados, sin columnas de personas | íntegra: huellas del criterio recalculadas al generar este informe y resultado aprobado sin IA | reconstruible: se vuelve a descargar con el contrato de datos (ingesta.py) y se compara con la procedencia |
| 2026-11-06-secop-medellin-2025 | publicable: barrido de datos personales limpio; solo agregados, sin columnas de personas | íntegra: huellas del criterio recalculadas al generar este informe y resultado aprobado sin IA | reconstruible: se vuelve a descargar con el contrato de datos (ingesta.py) y se compara con la procedencia |
| 2026-11-06-ventas-semestre | publicable: barrido de datos personales limpio; solo agregados, sin columnas de personas | íntegra: huellas del criterio recalculadas al generar este informe y resultado aprobado sin IA | reconstruible: datos sintéticos versionados y regenerables desde la semilla (generar_datos.py) |

Rutas locales del equipo del dueño en archivos versionados: 20 línea(s) en 12 archivo(s) (riesgo aceptado R07; la cifra no debe crecer).
