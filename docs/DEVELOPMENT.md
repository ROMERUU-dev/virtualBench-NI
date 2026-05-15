# Arquitectura y desarrollo

## Módulos principales

| Módulo | Responsabilidad |
| --- | --- |
| `gui.py` | Interfaz gráfica, validación y flujo de usuario |
| `instrument.py` | Adaptadores de hardware y simulación |
| `measurement.py` | Cálculo de amplitud, fase y ganancia |
| `sweep.py` | Generación y ejecución del barrido |
| `config.py` | Modelos de configuración |
| `cli.py` | Interfaz por consola |

## Diseño general

La aplicación separa tres capas:

1. **Presentación**: controles Tkinter y gráficas Matplotlib.
2. **Dominio de medición**: configuración, barrido y cálculo.
3. **Integración con hardware**: backend `pyvirtualbench` y simulador.

Esta separación permite:

- operar la GUI y el CLI con la misma lógica de barrido;
- probar cálculos sin depender del instrumento;
- aislar diferencias entre versiones de `pyvirtualbench`.

## Simulación

`SimulatedBackend` permite ejecutar el flujo sin hardware real y genera una respuesta tipo filtro RC para desarrollo y validación funcional.

## Empaquetado

La distribución para Windows se genera con PyInstaller usando:

- `packaging/windows/VBarrido.spec`;
- `scripts/build_windows.ps1`.

El build incluye `info.png` y los submódulos de `pyvirtualbench` para evitar fallos derivados de imports dinámicos.

## Recomendaciones para contribuir

- Mantén la lógica de medición fuera de la capa GUI cuando sea posible.
- Conserva validaciones de seguridad cerca de la operación de hardware.
- Actualiza la documentación cuando cambie el flujo de usuario.
- Verifica el modo simulado antes de probar con el equipo real.

## Comprobaciones útiles

```powershell
python -m compileall src
python -m vbarrido_py.cli --help
```

