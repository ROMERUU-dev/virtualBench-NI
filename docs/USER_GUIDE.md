# Guía de usuario

## Objetivo

`VBarrido` permite caracterizar la respuesta en frecuencia de un circuito usando un NI VirtualBench. La aplicación genera una señal senoidal, la mide antes y después del circuito y calcula:

- ganancia en V/V;
- ganancia en dB;
- fase relativa;
- trazas temporales de ambas señales.

## Flujo recomendado

1. Conecta el VirtualBench y abre la aplicación.
2. Verifica el estado del instrumento en la parte superior.
3. En **Inicio**, selecciona un preset de barrido adecuado.
4. Revisa el resumen previo a la medición.
5. Inicia el barrido.
6. Observa:
   - magnitud;
   - fase;
   - trazas temporales;
   - tabla de puntos medidos.
7. Exporta CSV, SVG o ambos desde **Datos de las gráficas**.

## Modos de interfaz

### Básico

Pensado para operación rápida. Mantiene disponibles:

- Inicio;
- Configuración Básica;
- Fuente DC;
- Información;
- Preferencias.

### Experto

Expone además:

- Configuración Avanzada;
- Datos de las gráficas.

Es el modo de inicio predeterminado.

## Presets de barrido

| Preset | Uso recomendado |
| --- | --- |
| Barrido rápido | Primera exploración del circuito |
| Barrido preciso | Medición más estable y detallada |
| Filtro RC | Filtros pasivos de primer orden |
| Amplificador | Etapas activas de banda amplia |
| Audio 20 Hz-20 kHz | Sistemas en banda audible |
| Diagnóstico amplio | Reconocimiento general del comportamiento |
| Resonancia estrecha | Picos o valles concentrados |
| Alta frecuencia | Circuitos rápidos y rango superior |

La interfaz muestra una ayuda breve para cada preset antes de aplicarlo.

## Fuente DC

La pestaña **Fuente DC** permite:

- habilitar o deshabilitar las salidas;
- ajustar `+25 V`, `-25 V` y `+6 V`;
- limitar corriente;
- exigir confirmación cuando se piden valores altos.

La salida inicia deshabilitada por seguridad.

## Exportación

### CSV

Incluye por punto:

- frecuencia;
- ganancia V/V;
- ganancia dB;
- fase;
- amplitud de referencia;
- amplitud de respuesta.

### SVG

Guarda la gráfica de respuesta en frecuencia en formato vectorial.

## Recomendaciones de medición

- Empieza con `1 Vpp` y `0 V` de offset.
- Usa tierra común entre generador, circuito y osciloscopio.
- Ajusta la atenuación de las puntas tanto en hardware como en software.
- Si el circuito tarda en estabilizarse, aumenta la espera entre puntos.
- Si hay ruido, aumenta promedios o ciclos por punto.

