"""Curated Home walkthrough. Only fixed, non-personal scripts reach TTS.

Shared audio caching is safe because neither member input nor household data is
part of these scripts. The existing Home voice ledger still bounds generation.
"""
from copy import deepcopy
import re

VERSION = 1


def chapter(key, title, subtitle, panel, icon, image, speech, steps, action, video=""):
    return dict(id=key, title=title, subtitle=subtitle, panel=panel, icon=icon,
                image=image, video=video, speech=speech, steps=steps, action=action)


CHAPTERS = [
    chapter("welcome", "Tu casa, a tu ritmo", "Soy Roxy. Vamos a conocernos.", "today", "home",
            "/assets/roxy_home_avatar.jpg",
            "Hola, soy Roxy. Estoy aquí para acompañarte en tu hogar: organizar tus días, cocinar contigo, cuidar tus plantas y mascotas, ayudarte a moverte, imaginar tus espacios y conectar con las personas que quieres. Vamos a descubrir cada rincón. Tú eliges por dónde empezar y puedes volver a esta guía cuando quieras.",
            ["Conoce los espacios de Home; cada uno tiene su propia guía.", "Escucha mi voz o lee la guía, a tu ritmo.", "Los permisos y las preguntas aparecen cuando decides usar cada función."], "Explorar mi Home", "/assets/roxy_home/tour/welcome.mp4"),
    chapter("appearance", "Una Roxy más tuya", "Tu nombre, tus colores y tu manera de conversar.", "more", "palette",
            "/assets/roxy_home_avatar.jpg",
            "Me gustaría que Home se sintiera tuyo. En Mi Roxy puedes elegir cómo te llamo, los colores de tu hogar, mi apariencia y el tamaño de letra. También puedes pedirme respuestas breves o explicaciones más detalladas. Guarda tus preferencias para encontrarlas cuando entres desde otro dispositivo.",
            ["Abre Más y entra en Mi Roxy.", "Elige nombre, tema, fondo, avatar y tamaño de letra.", "Selecciona mi estilo de respuesta y pulsa Guardar."], "Personalizar mi Roxy"),
    chapter("today", "Todo empieza por hoy", "Tu agenda, tu hogar y las pequeñas cosas importantes.", "today", "today",
            "/assets/roxy_home/home-hero-plant.png",
            "En Hoy reunimos lo que necesita tu atención: próximos eventos, el clima cuando compartes tu ubicación y los cuidados pendientes de tus plantas. También puedes organizar tus comidas de la semana. El botón Roxy abre nuestra conversación general: escribe lo que necesitas y te acompañaré desde aquí.",
            ["Mira tus próximos eventos y cuidados pendientes.", "Activa el clima con ubicación aproximada si lo deseas.", "Toca Roxy para conversar; Más reúne todas las secciones."], "Ir a Hoy"),
    chapter("recipes", "Cocinamos juntos", "Sabores, despensa y una guía paso a paso.", "recipes", "menu_book",
            "/assets/roxy_home/recipe_categories/proteins.jpg",
            "En Cocina puedes contarme tus gustos, los ingredientes que prefieres evitar y el tiempo que tienes. Explora comidas y bebidas, abre una receta y toca Preparar con Roxy para seguir los pasos. Revisa siempre los ingredientes. Cuando quieras llevarlos a Compra, te mostraré la lista para que decidas qué añadir.",
            ["Pulsa Personalizar para indicar idioma, gustos, alergias y tiempo disponible.", "Elige una comida o bebida y toca Preparar con Roxy.", "Avanza, repite un paso o pregunta. Añade ingredientes a Compra sólo cuando tú lo decidas."], "Explorar Cocina", "/assets/roxy_home/tour/kitchen.mp4"),
    chapter("shopping", "Compra con todo a mano", "Una lista compartida para tu hogar.", "shopping", "shopping_cart",
            "/assets/roxy_home/products/groceries.png",
            "En Compra reunimos lo que hace falta en casa. Puedes escribir un producto y su cantidad, o revisar los ingredientes que envías desde una receta. Ajusta las cantidades y, cuando termines, pulsa Compra hecha para archivar la lista. Añadir algo a la lista no realiza un pedido ni un pago.",
            ["Escribe el producto, revisa cantidad y unidad, y añádelo.", "Ajusta cantidades con los botones de más y menos. Al terminar, Compra hecha archiva la lista completa.", "Desde una receta, revisa los ingredientes antes de confirmar su incorporación."], "Abrir mi lista"),
    chapter("pantry", "Lo que ya tienes", "Tu despensa también cuenta.", "pantry", "kitchen",
            "/assets/roxy_home/products/vegetables.png",
            "En Despensa puedes registrar los ingredientes que ya tienes, sus cantidades y unidades. Mantenerla al día te ayuda a revisar lo disponible antes de cocinar o preparar una compra. Puedes corregir cada cantidad cuando uses un ingrediente.",
            ["Entra desde Más → Despensa.", "Escribe un producto por línea: nombre; cantidad; unidad.", "Guardar despensa reemplaza la lista compartida: conserva en el campo todos los productos que todavía tienes."], "Ver mi despensa"),
    chapter("fitness", "Un momento para moverte", "Guías en español y espacio en tu agenda.", "fitness", "exercise",
            "/assets/roxy_home/fitness/roxy-fitness-welcome.jpg",
            "Ejercicio te ayuda a explorar movimientos y guías generales de fuerza suave, equilibrio y flexibilidad. Puedes leer cada movimiento en español, elegir tus días y reservar una actividad en el calendario de Home después de revisarla. Las guías conservan sus fuentes. El entrenamiento personalizado todavía necesita su revisión profesional; estas guías no evalúan tu salud.",
            ["Pulsa Organizar mis días y abre una guía de fuerza, equilibrio o flexibilidad.", "Selecciona fecha y días; revisa cada movimiento y su fuente.", "Reserva una actividad desde la guía, revisa hora y duración y confirma en Calendario."], "Explorar Ejercicio"),
    chapter("design", "Imagina tu próximo espacio", "Renueva empieza con lo que ya amas de tu casa.", "design", "chair",
            "/assets/roxy_home/renueva-living-room-hero.webp",
            "En Renueva empezamos con una foto de tu habitación. Cuéntame qué quieres conservar, qué cambiarías, las medidas que conoces, el estilo y tu presupuesto. Así puedes organizar tu proyecto y revisar propuestas cuando la generación esté disponible en tu cuenta. Tú decides los cambios y cualquier compra por separado.",
            ["Pulsa Subir imágenes; en el formulario añade una foto clara de la habitación.", "Indica estancia, estilo, presupuesto, medidas y lo que quieres conservar.", "Revisa tu proyecto y las propuestas disponibles antes de decidir materiales o compras."], "Conocer Renueva"),
    chapter("plants", "Cada planta tiene su historia", "Su luz, sus raíces y tus observaciones.", "plants", "potted_plant",
            "/assets/roxy_home/home-hero-plant.png",
            "En Jardín vamos a conocer cada planta. Añade una foto, su nombre y dónde vive; después cuéntame qué luz recibe y si está en tierra o en agua. Podrás revisar su ficha y registrar tus observaciones. Marcar una revisión no significa regar: primero observa lo que tu planta necesita.",
            ["Añade una planta con foto, nombre y especie si la conoces.", "Describe su ubicación, luz, sustrato, maceta y drenaje.", "Abre su revisión para registrar observaciones y el cuidado que realmente hiciste."], "Entrar en mi jardín", "/assets/roxy_home/tour/garden.mp4"),
    chapter("pets", "Ellos también son familia", "Una ficha y cuidados para cada compañero.", "pets", "pets",
            "/assets/roxy_home/pet-onboarding-hero.png",
            "En Mascotas creamos una ficha para cada compañero, según su especie. Puedes registrar edad, alimentación, entorno, alergias conocidas y las indicaciones de su veterinario. Consulta sus cuidados y registra lo que haces. Para una cita veterinaria, abre Calendario y revisa los datos antes de confirmarla.",
            ["Añade una mascota: especie, nombre, edad y los datos que conozcas.", "Completa alimentación, salud, entorno y rutinas; conserva las indicaciones veterinarias.", "Consulta su ficha, historial y cuidados. Usa Calendario para sus próximas citas."], "Conocer Mascotas", "/assets/roxy_home/tour/dog.mp4"),
    chapter("family", "Cerca de quienes quieres", "Nexo conecta con tu permiso.", "family", "hub",
            "/assets/roxy_home/tour/nexo-connection.png",
            "Nexo es el espacio para conectar con las personas de tu hogar. Revisa tu perfil y decide si quieres compartir ubicación. Cada persona activa su propio permiso. Una conexión de Nexo tiene un alcance distinto del acceso completo a tu hogar. Antes de invitar a alguien, revisa qué acceso le estás dando.",
            ["Abre Nexo y revisa tu perfil y las conexiones disponibles.", "Revisa el alcance de una invitación antes de compartirla.", "Decide si deseas compartir ubicación; puedes detenerla desde los controles de Nexo."], "Abrir Nexo"),
    chapter("location", "Tu ubicación, bajo tu control", "Te acompaño al activar el permiso.", "family", "location_on",
            "/assets/roxy_home/tour/nexo-connection.png",
            "Para activar tu ubicación, entra en Nexo y toca Activar ubicación permanente. Home recordará tu elección y actualizará tu posición mientras uses la aplicación. Tu navegador te pedirá permiso: elige permitir si quieres compartirla. Si antes la bloqueaste, abre los permisos de este sitio y cambia Ubicación a Permitir; en el teléfono también revisa los permisos del navegador en Ajustes. Después vuelve a Home y reintenta. El clima usa su propio botón en Hoy.",
            ["En Nexo, toca Activar ubicación permanente y responde al permiso. La web actualiza tu posición mientras está en uso.", "Si está bloqueado: permisos del sitio → Ubicación → Permitir. En el móvil revisa también Ajustes → permisos del navegador.", "Vuelve a Home y reintenta. Comprueba que aparezca una ubicación reciente; puedes detener el uso desde Nexo.", "Para el clima, usa Hoy → Activar ubicación aproximada. No se activa al ver esta guía."], "Ver controles de ubicación"),
    chapter("calendar", "Hazle un lugar en tu día", "Eventos y recordatorios, revisados por ti.", "calendar", "event",
            "/assets/roxy_home/home-hero-plant.png",
            "En Calendario puedes añadir una cita, una actividad, un cuidado o un compromiso de casa. Toca Agregar evento, escribe el título y elige fecha, hora, duración y aviso. Revisa la repetición y las personas que incluyes. Antes de guardarlo te enseñaré un resumen y los posibles cruces de horario. Confirma cuando todo esté bien. Puedes exportar un evento para importarlo en otro calendario.",
            ["Pulsa Agregar evento y escribe título, fecha, hora y duración.", "Elige recordatorio, categoría, repetición y fecha final si se repite.", "Revisa el resumen y los conflictos; pulsa Sí, programar para guardarlo.", "Abre un evento guardado para editarlo o descargarlo e importarlo en tu calendario."], "Crear un evento"),
]

# These are guidance scripts, not a reading of a person's private form values.
EXTRA_SCRIPTS = {
    "timer-finished": "Tu temporizador ha terminado. Comprueba la preparación antes de continuar.",
    "recipe-0": "Vamos a conocer tus sabores. Elige español o inglés para tus recetas. Puedes indicar tu país de origen y escoger entre sabores de casa, una mezcla o las cocinas que te interesen. Los datos personales son opcionales.",
    "recipe-1": "Cuéntame tus gustos. Puedes indicar cómo comes, tus alimentos favoritos, lo que prefieres evitar y las alergias que quieras registrar. Revisa siempre los ingredientes y sus etiquetas: un filtro no certifica ausencia de alérgenos.",
    "recipe-2": "Ahora, tu ritmo. Indica cuánto tiempo sueles tener para cocinar y cómo te sientes en la cocina. También puedes dejar estas preguntas sin responder.",
    "recipe-3": "Revisa tu ficha de cocina. Puedes volver atrás para cambiar cualquier respuesta. Confirma el permiso de guardado cuando estés de acuerdo. Podrás editar tus gustos más adelante desde Cocina.",
    "garden-0": "Vamos a conocer a tu planta. Añade una foto clara y el nombre con el que quieres recordarla. Indica la especie si la conoces; si no, podremos revisar su identificación cuando esa función esté disponible.",
    "garden-1": "Cuéntame dónde vive tu planta. Indica la habitación, si está dentro o fuera y la luz que recibe. Piensa en las condiciones reales de ese lugar, no sólo en las de hoy.",
    "garden-2": "Ahora miramos sus raíces. Indica si crece en tierra, sustrato o agua, el tipo de maceta y si tiene drenaje. Cada entorno requiere cuidados distintos.",
    "garden-3": "Revisa la ficha antes de guardarla. Podrás corregir sus datos después y registrar tus observaciones en cada revisión. No hace falta regar para completar una revisión.",
    "garden-review": "Observa las hojas, el sustrato o el agua y las raíces visibles. Cuéntame qué ves y marca únicamente el cuidado que hiciste. Puedes añadir una foto. Esta revisión se guarda en su historial.",
}


def catalogue():
    return {"version": VERSION, "chapters": deepcopy(CHAPTERS)}


def speech_for(key):
    match = re.fullmatch(r"fitness:(strength|balance|flexibility):([0-9])", key or "")
    if match:
        from roxy_os.fitness.programs import program_detail
        program = program_detail("gentle-" + match[1])["program"]
        index = int(match[2])
        if index >= len(program["exercises"]):
            return None
        exercise = program["exercises"][index]
        return " ".join(["Guía general, adaptación en español de un original del NHS.",
                         exercise["name_es"] + ".", *exercise["instructions_es"],
                         "Si sientes dolor, detén el movimiento."])
    if key in EXTRA_SCRIPTS:
        return EXTRA_SCRIPTS[key]
    return next((row["speech"] for row in CHAPTERS if row["id"] == key), None)


def normalize_progress(value):
    if not isinstance(value, dict) or set(value) != {"version", "chapter", "completed"}:
        raise ValueError("El recorrido no es válido.")
    if type(value["version"]) is not int or value["version"] != VERSION or type(value["completed"]) is not bool:
        raise ValueError("Actualiza Home para guardar este recorrido.")
    if value["chapter"] not in {row["id"] for row in CHAPTERS}:
        raise ValueError("El capítulo no es válido.")
    return deepcopy(value)
