# VirtualBench NI Frequency Sweep

Aplicación de escritorio en Python para realizar barridos frecuenciales con **NI VirtualBench**, visualizar la respuesta en frecuencia y controlar las fuentes DC integradas del equipo.

El proyecto replica y moderniza el flujo de trabajo de un analizador de Bode:

- generación senoidal mediante FGEN;
- adquisición dual con MSO;
- cálculo de ganancia y fase por tono;
- visualización de magnitud, fase y trazas temporales;
- exportación de resultados a CSV y SVG;
- control seguro de las salidas de fuente DC.

## Características principales

- Interfaz gráfica con modos **Básico** y **Experto**.
- Inicio por defecto en **modo experto** y **tema claro**.
- Presets de barrido con ayudas contextuales.
- Control de fuente DC disponible también en modo básico.
- Detección automática del instrumento VirtualBench.
- Exportación de resultados para análisis posterior.
- Backend de simulación para desarrollo sin hardware conectado.

## Descarga para Windows

El ejecutable listo para usar se distribuye como:

```text
dist/VBarrido.exe
```

Para uso con hardware real, la computadora debe tener instalados:

1. NI VirtualBench / controladores requeridos por el equipo.
2. El acceso al dispositivo VirtualBench por USB.

La aplicación incluye el código Python empaquetado, pero depende del entorno de drivers del sistema para comunicarse con el hardware.

## Inicio rápido

### Con ejecutable

1. Descarga `VBarrido.exe`.
2. Conecta el VirtualBench por USB.
3. Ejecuta la aplicación.
4. Verifica el recurso detectado.
5. Selecciona un preset o ajusta el barrido manualmente.
6. Inicia la medición y exporta los resultados.

### Desde código fuente

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
vbarrido-gui
```

Para habilitar hardware real:

```powershell
python -m pip install -e .[hardware]
```

## Uso por consola

```powershell
vbarrido --config examples\config.toml --output sweep.csv
```

Modo de simulación para desarrollo:

```powershell
vbarrido --config examples\config.toml --simulate --output sweep_sim.csv
```

## Documentación

- [Guía de usuario](docs/USER_GUIDE.md)
- [Instalación y distribución](docs/INSTALLATION.md)
- [Arquitectura y desarrollo](docs/DEVELOPMENT.md)
- [Seguridad y conexión de hardware](docs/HARDWARE.md)

## Estructura del proyecto

```text
src/vbarrido_py/        Código fuente principal
examples/               Configuraciones de ejemplo
analysis/               Notas técnicas del comportamiento inferido
docs/                   Documentación del proyecto
packaging/windows/      Archivos para generar el ejecutable
scripts/                Automatización de build
dist/                   Ejecutable compilado para Windows
```

## Validación recomendada

Antes de medir un circuito real, conecta temporalmente la salida del generador a ambos canales del MSO:

- la ganancia debe quedar cercana a `0 dB`;
- la fase debe quedar cercana a `0°`.

Ese chequeo confirma que la cadena de medición está bien configurada antes de introducir el circuito bajo prueba.

## Estado del proyecto

Versión actual: `0.1.0`

El proyecto está orientado a uso de laboratorio y puede seguir evolucionando con mejoras de empaquetado, pruebas automatizadas y compatibilidad adicional con variantes del paquete `pyvirtualbench`.
