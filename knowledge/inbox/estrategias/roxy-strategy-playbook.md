# Roxy Strategy Playbook

category: estrategias-internas

Objetivo: cada estrategia debe tener condiciones de entrada, invalidacion, stop, target, ratio riesgo/recompensa y estado operativo. Roxy no debe decir "comprar" si no puede explicar por que, donde entra, donde se equivoca y donde toma ganancia.

## EMA Cross

Entrada valida cuando EMA9 cruza EMA21 o EMA20 con precio rompiendo estructura y volumen superior al promedio. Confirmar que el precio no este extendido. Stop bajo el ultimo minimo relevante para largos o sobre el ultimo maximo para cortos. Evitar cruces dentro de rango lateral.

## Pullback

Buscar tendencia definida, retroceso ordenado hacia EMA/VWAP/zona de soporte y vela de rechazo. La entrada debe ocurrir despues de confirmacion, no durante la caida. Target inicial en maximo previo o extension medida. Invalidacion si el pullback rompe estructura.

## Breakout

Requiere rango claro, compresion previa, aumento de volumen y cierre fuera del nivel. Evitar breakouts con velas agotadas y sin retest cuando el stop queda demasiado lejos. Roxy debe marcar si es breakout listo, esperar retest o no operar.

## Reversal

Solo buscar reversals cuando exista agotamiento, divergencia o rechazo fuerte en zona clave. Requiere stop pequeno y confirmacion clara. Evitar intentar atrapar techos o pisos sin senal objetiva.

## ORB

Opening Range Breakout define el rango inicial y opera ruptura con volumen y direccion del mercado. Roxy debe considerar noticias, gap, tendencia del indice y volatilidad. Si el rango es demasiado amplio, el riesgo puede invalidar la operacion.
