# Jardín: mango y romero — 10 de septiembre de 2026

Estado: dos perfiles implementados y verificados en pruebas locales; no es una
comprobación de producción ni de una planta real del hogar.

## Fuentes inspeccionadas

Mango — *Mangifera indica*:

- [UF/IFAS, guía de cultivo en el jardín de Florida](https://ask.ifas.ufl.edu/publication/MG216): diferencias por establecimiento, edad y vigor; separación y drenaje.
- [UF/IFAS Gardening Solutions, Mango](https://gardeningsolutions.ifas.ufl.edu/plants/edibles/fruits/mango/): identidad, luz y alcance climático.
- [UF/IFAS, factores ambientales, tabla 10](https://ask.ifas.ufl.edu/publication/HS1499): rango óptimo publicado, distinguido de un umbral seguro o lectura de sensor.

Romero — *Salvia rosmarinus* (sinónimo *Rosmarinus officinalis*):

- [UF/IFAS Gardening Solutions, Rosemary](https://gardeningsolutions.ifas.ufl.edu/plants/edibles/vegetables/rosemary/): luz, drenaje, porte y cultivo en recipiente.
- [University of Illinois Extension, Rosemary](https://extension.illinois.edu/herbs/rosemary): identificación y contexto de macetas/invierno.
- [ASPCA, Rosemary](https://www.aspca.org/pet-care/aspca-poison-control/toxic-and-non-toxic-plants/rosemary): afirmación de no toxicidad limitada a perros, gatos y caballos; no extrapolada a extractos u otras mascotas.

## Implementación

`home_plants.py`: `PLANT_CATALOG`, `PLANT_ENVIRONMENT` y fuentes por especie.
`public_plant` entrega `space`, `container_notes`, `care_scope`,
`source_reviewed_on`, `reminder_scope` y las fuentes correspondientes. No aplica
una guía genérica de planta de interior como fuente de mango. No se asignan dosis
de fertilizante, volúmenes universales de maceta, fechas de cosecha ni garantías.

Las fechas internas son comprobaciones sugeridas por Roxy, no una frecuencia
de riego avalada por esos autores. Para mango, la antigua tarea de girar maceta
se sustituye por revisión de luz y espacio del árbol. Una ubicación declarada
sin sol directo muestra la incompatibilidad potencial con una ficha de pleno
sol, no un diagnóstico. El dato de seguridad del mango para mascotas permanece
desconocido; no se etiqueta como alimento ni planta universalmente segura.

No se reidentifican plantas existentes por su apodo. Una planta antes guardada
como desconocida necesita confirmación de especie. Se conservan los límites
de medio desconocido/agua; una nueva entrada no habilita cultivo hidropónico.

## Validación

46 pruebas aprobadas entre `test_roxy_home_garden_edibles.py` (6 casos),
`test_roxy_home_garden_journal.py` (19) y `test_roxy_home_plants.py` (21).
Incluyen selección/persistencia, fuentes, agua frente a suelo, datos desconocidos,
preservación, alcance de toxicidad, estado privado y títulos de tareas.
`git diff --check` aprobado. No llamadas de identificación pagadas, medios
externos reutilizados, datos públicos cambiados ni módulos ajenos a Home editados.
