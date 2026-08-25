# Clima en Roxy Home

Roxy Home consulta el pronóstico desde el servidor. La clave del proveedor no
se incluye en HTML, JavaScript ni en la PWA. La ubicación es opcional: el
usuario debe activarla desde su perfil y el navegador guarda únicamente las
coordenadas aproximadas ya redondeadas por Roxy Home. No se usa seguimiento
continuo.

## Experiencia

- **Hoy** muestra temperatura, condiciones, rango del día y lluvia.
- **Calendario** añade un símbolo del tiempo a los días cubiertos por el
  pronóstico y un resumen en cada agenda diaria.
- **Roxy** entiende preguntas como «¿qué probabilidad de lluvia hay el domingo
  en Daytona Beach?» y consulta el destino indicado.
- Para fechas fuera de la ventana disponible, Roxy lo informa y no inventa un
  pronóstico.
- El último pronóstico correcto queda en la caché local para una lectura básica
  sin conexión, identificado como información previamente sincronizada.

## Configuración en Render

```dotenv
ROXY_HOME_WEATHER_API_URL=https://api.open-meteo.com/v1/forecast
ROXY_HOME_WEATHER_GEOCODING_URL=https://geocoding-api.open-meteo.com/v1/search
ROXY_HOME_WEATHER_API_KEY=
ROXY_HOME_WEATHER_TIMEOUT_SECONDS=10
ROXY_HOME_WEATHER_CACHE_SECONDS=900
```

Los endpoints deben ser HTTPS. Antes de vender Roxy Home, se debe contratar o
confirmar un plan/licencia que permita el uso comercial previsto y configurar
el endpoint de cliente correspondiente. Como alternativa futura, la app nativa
para iPhone puede usar WeatherKit, manteniendo la misma respuesta normalizada
de `/v1/home-weather/{usuario}`.

El pronóstico es orientativo. Para huracanes, tormentas severas, navegación,
salud o decisiones sensibles, la interfaz debe remitir a alertas oficiales.
