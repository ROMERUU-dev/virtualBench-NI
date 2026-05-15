# Instalación y distribución

## Requisitos

### Para ejecutar el `.exe`

- Windows 10 u 11.
- NI VirtualBench instalado y funcional.
- Conexión USB al instrumento.

### Para desarrollar desde fuente

- Python `>= 3.10`.
- `pip`.
- Dependencias definidas en `pyproject.toml`.

## Instalación desde fuente

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Para soporte de hardware:

```powershell
python -m pip install -e .[hardware]
```

## Compilación del ejecutable

El proyecto incluye un script de build:

```powershell
.\scripts\build_windows.ps1
```

Ese script genera:

```text
dist/VBarrido.exe
```

## Qué incluye el ejecutable

- Código de la aplicación.
- Dependencias Python necesarias.
- Recursos visuales del proyecto.

## Qué no reemplaza el ejecutable

El `.exe` no sustituye los controladores del fabricante. Para hablar con el equipo real, Windows debe tener disponible el entorno de NI VirtualBench y las bibliotecas asociadas.

## Verificación posterior al build

1. Ejecuta `dist/VBarrido.exe`.
2. Confirma que la interfaz abre correctamente.
3. Verifica que:
   - el tema inicial sea claro;
   - el modo inicial sea experto;
   - estén visibles las pestañas esperadas;
   - el panel de información cargue la imagen del proyecto.

