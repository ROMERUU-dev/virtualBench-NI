# Especificacion funcional inferida

## Flujo de la aplicacion original

1. Seleccionar dispositivo VirtualBench.
2. Configurar FGEN:
   - Forma de onda: seno.
   - Amplitud: configurable.
   - Offset DC: configurable.
   - Frecuencia: cambia en cada paso del barrido.
3. Configurar MSO:
   - Canales analogicos: CH1 y CH2.
   - Trigger analogico por borde.
   - Sample rate aproximado: `10 * frecuencia`, con coercion a limites del MSO.
4. Para cada frecuencia:
   - Configurar FGEN a esa frecuencia.
   - Ejecutar/adquirir MSO.
   - Extraer ambas formas de onda.
   - Medir tono en CH1 y CH2: amplitud, fase, frecuencia.
   - Calcular resultados:
     - `gain_v = amp_ch1 / amp_ch2`
     - `gain_db = 20 * log10(gain_v)`
     - `phase_deg = phase_ch1 - phase_ch2`
     - Si la fase queda negativa, aplicar correccion equivalente a envolverla al rango deseado.
   - Guardar/plotea frecuencia, ganancia dB y fase.
5. Cerrar sesiones FGEN/MSO.

## Barrido exponencial

Usar frecuencias logaritmicamente espaciadas:

```python
frequencies = numpy.geomspace(start_hz, stop_hz, points)
```

Esto corresponde a la nota del VI: "Exponentially ramp the signal to sweep through...".

## Criterios de paro vistos en el VI

- No se detecta senal/trigger.
- Frecuencia fuera de rango.
- Senal atenuada por debajo de -30 dB.

## Validacion esperada

Comparar un CSV generado por Python contra mediciones de LabVIEW en un circuito simple:

- Cable directo: ganancia cercana a 0 dB y fase cercana a 0 grados.
- Filtro RC: curva Bode con pendiente y fase esperadas.
