# Seguridad y conexión de hardware

## Conexión recomendada

1. Conecta la salida del generador de funciones al canal de referencia.
2. Alimenta con la misma señal la entrada del circuito bajo prueba.
3. Conecta la salida del circuito al canal de respuesta.
4. Mantén tierra común entre:
   - generador;
   - circuito;
   - osciloscopio.

## Fuente DC

La aplicación permite controlar los rieles:

- `+25 V`;
- `-25 V`;
- `+6 V`.

Por seguridad:

- la salida inicia apagada;
- se valida el rango de tensión;
- se valida el límite de corriente;
- se solicita confirmación para configuraciones altas.

## Límites prácticos

- Empieza con amplitudes moderadas.
- Evita saturar la entrada del circuito o del MSO.
- Usa puntas configuradas con la atenuación correcta.
- Si el circuito es sensible, aumenta gradualmente tensión y amplitud.

## Validación inicial

Antes de medir el circuito final:

1. Conecta la misma señal a ambos canales.
2. Ejecuta un barrido corto.
3. Comprueba:
   - ganancia cercana a `0 dB`;
   - fase cercana a `0°`.

Si esa prueba falla, revisa cableado, atenuación de puntas, trigger y recurso del instrumento antes de continuar.

