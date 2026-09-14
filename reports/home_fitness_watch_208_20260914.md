# Ejercicio 208: Apple Watch y límites de la web

Consulta del 14-09-2026, exclusivamente con documentación oficial de Apple.
Es una propuesta técnica; no se instaló un SDK ni se activó ninguna integración.

## Qué podemos construir

| Experiencia | Implementación necesaria |
|---|---|
| Plan casa/gimnasio, días, minutos, material y resultados declarados | La web/PWA actual puede ofrecer formularios, agenda y progreso propios. |
| Importar entrenamientos ya realizados con Apple Watch | Aplicación iOS de Roxy Home con HealthKit y autorización de la persona; puede leer los entrenamientos que lleguen a Salud. No exige comenzar creando una aplicación watchOS propia. |
| Sesión Roxy en el reloj, con inicio/pausa/fin y métricas durante la actividad | Aplicación watchOS con `HKWorkoutSession`/`HKLiveWorkoutBuilder`; puede reflejar la sesión en su aplicación iOS compañera. |
| Enviar entrenamientos compatibles a Entreno de Apple Watch | Evaluar WorkoutKit: permite crear, previsualizar y sincronizar sesiones y agenda con permiso. No implica que admita cualquier rutina de fuerza, máquina o registro de series; hay que verificar cada modalidad. |

**La PWA por sí sola no obtiene Salud ni el pulso del reloj.** Esta es la
conclusión de arquitectura a partir de las superficies nativas documentadas:
HealthKit exige la capacidad de aplicación, autorización del sistema y comprobar
disponibilidad en el dispositivo. Apple no documenta aquí una API JavaScript o
REST para que el sitio consulte el almacén de Salud directamente. Instalar la
web en la pantalla de inicio no le añade esa capacidad.
[Disponibilidad de HealthKit](https://developer.apple.com/documentation/healthkit/hkhealthstore/ishealthdataavailable()),
[configuración y autorización](https://developer.apple.com/documentation/healthkit/authorizing-access-to-health-data).

La sesión propia debe empezar en el reloj para aprovechar sus métricas. El
ejemplo oficial de comunicación reloj–iPhone requiere dispositivos físicos y
aprovisionamiento de sus aplicaciones. No hay que confundir reflejar una sesión
nativa con transmitirla directamente a una pestaña web.
[Sesión de entrenamiento](https://developer.apple.com/documentation/healthkit/hkworkoutsession),
[ejemplo multidispositivo](https://developer.apple.com/documentation/healthkit/building-a-multidevice-workout-app),
[WorkoutKit](https://developer.apple.com/documentation/workoutkit).

## Datos y permisos mínimos

Solicitar lectura por separado para entrenamientos, energía activa y, si la
persona quiere verla, frecuencia cardiaca. Peso (`bodyMass`) y estatura
(`height`) son opciones independientes: son valores existentes en Salud, no
mediciones corporales que haga el reloj por sí solo. La alternativa manual
debe seguir disponible. Pedir escritura únicamente si una función elegida
guardará sesiones o muestras en Salud; importar no requiere escribir.
[Tipos de datos](https://developer.apple.com/documentation/healthkit/data-types),
[autorización por tipo y dirección](https://developer.apple.com/documentation/healthkit/authorizing-access-to-health-data).

No mostrar «permiso denegado» ni cero calorías porque una consulta venga vacía:
HealthKit limita qué puede conocer la aplicación sobre permisos de lectura y
puede permitir solo una ventana reciente. Usar «Sin datos disponibles» y mostrar
la fecha de última sincronización. El bloqueo del teléfono puede limitar
lecturas en segundo plano; no prometer sincronización continua inmediata.
[Autorización](https://developer.apple.com/documentation/healthkit/authorizing-access-to-health-data),
[protección de privacidad](https://developer.apple.com/documentation/healthkit/protecting-user-privacy).

## Calorías, pulso y resultados

La interfaz debe decir **«Calorías activas estimadas · Apple Watch»**, con unidad,
periodo y procedencia. Apple usa datos personales como peso, estatura y edad;
el ajuste del reloj y la calibración afectan las mediciones. No hay respaldo
para prometer precisión individual exacta ni convertir calorías en una
prescripción alimentaria automática.
[Mediciones del Apple Watch](https://support.apple.com/en-us/105002).

Energía activa excluye la energía en reposo. No sumar otra vez las mismas
muestras al total del entrenamiento. Para sesiones importadas, usar las
estadísticas de HealthKit por tipo; un valor ausente sigue ausente.
`HKWorkout.totalEnergyBurned` está deprecado: Apple remite a estadísticas.
[Energía activa](https://developer.apple.com/documentation/healthkit/hkquantitytypeidentifier/activeenergyburned),
[estadísticas](https://developer.apple.com/documentation/healthkit/hkworkout/statistics(for:)),
[propiedad deprecada](https://developer.apple.com/documentation/healthkit/hkworkout/totalenergyburned).

El pulso y la energía registrados no prueban que se completó cada repetición
de una rutina. Mantener separados los resultados declarados —series, repeticiones,
carga, esfuerzo— de los datos importados. Esto es una decisión propuesta para
Roxy, no una capacidad automática atribuida a Apple.

## Arquitectura mínima propuesta para Home

1. Conector iOS de Roxy Home → autorización HealthKit → resumen local de sesión.
2. Consentimiento distinto para sincronizar ese resumen con **el perfil personal
   de Home**. Endpoint autenticado y almacenamiento privado con RLS; nunca el
   calendario compartido, otro producto Roxy, publicidad o una petición a IA por
   defecto. Se conserva el uso manual sin conectar el reloj.
3. Guardar solo identificador de origen, intervalo, tipo, duración y métricas
   elegidas; pulso resumido antes que toda la serie si basta para la función.
   Diferenciar fuente, unidades, hora del dato y hora de importación.
4. Importación idempotente por miembro y objeto; procesar altas y eliminaciones
   con consultas ancladas. Los reintentos no duplican sesiones ni calorías.
5. Desconectar detiene futuras importaciones; eliminar los datos importados en
   Home es una acción explícita y no borra automáticamente los originales de
   Salud. El usuario puede exportar sus datos privados.

Estas son decisiones de diseño para el aislamiento ya exigido por Roxy.
Apple requiere uso claro para salud/fitness, permisos expresos para compartir
con terceros y prohíbe usar datos HealthKit para segmentación publicitaria o
venderlos. Las consultas ancladas entregan objetos añadidos y eliminados.
[Privacidad de HealthKit](https://developer.apple.com/documentation/healthkit/protecting-user-privacy),
[sincronización incremental](https://developer.apple.com/documentation/healthkit/hkanchoredobjectquery).

Primera entrega aconsejada: plan y registro funcionales en web; después importador
iOS de sesiones existentes; por último sesión propia del reloj si aporta valor.
HealthKit aporta datos y sesiones: **no genera por sí mismo un programa personal
para casa o gimnasio**. Esa lógica y su validación son trabajo de Roxy aparte.
