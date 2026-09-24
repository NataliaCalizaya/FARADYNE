# FARADYNE — Frontend React + Tailwind CSS

Sistema de Diseño y Cálculo de Instalaciones de Protección contra Descargas Atmosféricas (SPDA).

## Requisitos Previos
- Node.js (v18.x o superior)
- npm (v9.x o superior)
- Backend de FARADYNE corriendo en paralelo en `http://127.0.0.1:8000`

## Instalación

1. Navegar a la carpeta `frontend/`:
   ```bash
   cd frontend
   ```

2. Instalar dependencias:
   ```bash
   npm install
   ```

## Configuración de Variables de Entorno

Crear/verificar el archivo `.env` en la raíz de `frontend/`:
```env
VITE_API_BASE_URL=http://127.0.0.1:6500/api/v1
```

## Ejecución en Desarrollo

Levantar el servidor de desarrollo Vite:
```bash
npm run dev
```

La aplicación se abrirá en `http://localhost:1232`.

## Compilación para Producción

Para construir el bundle de producción:
```bash
npm run build
```

## Mapeo de Historias de Usuario e Integración Backend

- **Paso 1 (Datos del Proyecto)**: Placeholder visual para el registro del proyecto.
- **Paso 2 (HU02 - Cargar Plano)**: `POST /api/v1/planos` (archivos DXF y PDF).
- **Paso 3 (HU02 - Validar Geometría)**: `GET /api/v1/planos/{id}/preview` e interfaz de edición 2D.
- **Paso 4 (HU04 - Nivel de Protección)**: `POST /api/v1/niveles-proteccion` (cálculo de $N_d$, $N_c$ y SPCR según IEC 62305).
- **Paso 5 (HU05 + HU03 - Ubicación Mástiles y Visor 3D)**:
  - `POST /api/v1/mastiles` para crear mástiles captores.
  - `PUT /api/v1/mastiles/{id}` y `DELETE /api/v1/mastiles/{id}`.
  - `GET /api/v1/mastiles/proyecto/{idProyecto}/cobertura` para porcentaje de cobertura y esfera rodante.
  - `POST /api/v1/modelos3d` y `GET /api/v1/modelos3d/{id}` con visor Three.js `@react-three/fiber` + `OrbitControls`.
- **Paso 6 (Listado de Materiales)**: Placeholder visual con marca `// TODO: conectar cuando exista el endpoint`.
- **Paso 7 (Memoria Descriptiva)**: Placeholder visual con marca `// TODO: conectar cuando exista el endpoint`.
