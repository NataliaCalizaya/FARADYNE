# FARADYNE — Backend MVC (Python + FastAPI + PostgreSQL)

Sistema de Protección contra Descargas Atmosféricas (SPDA) según normativa **IEC 62305 / IRAM 2184**.

---

## 🚀 Arquitectura y Tecnologías
- **Core**: Python 3.12 / FastAPI
- **Base de Datos**: PostgreSQL + `psycopg2` (Consultas SQL 100% parametrizadas `%s`, **sin ORM auto-migratorio**)
- **Validación de Schemas**: `pydantic` v2 / `pydantic-settings`
- **Cad & Geometría**: `ezdxf` (Lectura y parseo de planos DXF/PDF), `numpy` (Interpolación vectorial de pendientes e inclinación de cubiertas)
- **Pruebas Unitarias**: `pytest`

---

## 📁 Estructura del Proyecto

```
backend/
├── app/
│   ├── main.py                          # Punto de entrada FastAPI y lifespan events
│   ├── core/
│   │   ├── config.py                    # Configuración BaseSettings desde .env
│   │   └── database.py                  # Connection Pool psycopg2 y verificación inicial DB
│   ├── models/                          # Dataclasses de entidades DB (proyecto, plano, modelo2d, modelo3d, etc.)
│   ├── schemas/                         # Schemas Pydantic para endpoints (plano, modelo3d, nivel_proteccion, mastil)
│   ├── repositories/                    # Consultas SQL parametrizadas (%s) por entidad
│   ├── services/
│   │   ├── dxf_interpreter_service.py   # Interpretación y parseo DXF con ezdxf
│   │   ├── model3d_generator_service.py # Extrusión determinística 2D -> 3D e interpolación Z con numpy
│   │   └── spda_service.py              # Fórmulas normativas Ae, Nd, Nc y Esfera Rodante
│   └── api/
│       └── v1/
│           ├── router.py                # Enrutador central /api/v1
│           └── endpoints/
│               ├── planos.py            # HU02: Cargar plano DXF/PDF y vista previa
│               ├── modelos3d.py         # HU03: Extrusión 3D determinística y vista por defecto
│               ├── niveles_proteccion.py# HU04: Cálculo de riesgo SPDA (Ae, Nd, Nc)
│               └── mastiles.py          # HU05: Posicionamiento y cobertura de mástiles captores
├── tests/                               # Tests unitarios con pytest
│   ├── test_model3d_generator.py        # Pruebas de extrusión e interpolación de pendiente
│   └── test_spda.py                     # Pruebas de fórmulas normativas SPDA
├── schema.sql                           # Referencia DDL SQL de las 9 tablas
├── requirements.txt                     # Dependencias pip
├── .env.example                         # Plantilla de variables de entorno
└── README.md
```

---

## 🛠️ Instalación y Configuración

### 1. Crear y activar entorno virtual
```bash
# En Windows (PowerShell):
python -m venv venv
.\venv\Scripts\Activate.ps1

# En Linux/macOS:
python3 -m venv venv
source venv/bin/activate
```

### 2. Instalar dependencias
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configurar variables de entorno
Copie la plantilla `.env.example` a un archivo `.env` en la raíz de `backend/`:
```bash
cp .env.example .env
```
Ajuste las credenciales de PostgreSQL en `.env`:
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=faradyne
DB_USER=postgres
DB_PASSWORD=tu_contraseña_aqui
```

### 4. (Opcional) Inicializar Base de Datos
Si la base de datos `faradyne` no contiene las tablas aún, puede ejecutarse `schema.sql` en PostgreSQL:
```bash
psql -U postgres -d faradyne -f schema.sql
```

---

## ⚡ Ejecución del Servidor Backend

Para iniciar el servidor en modo desarrollo con auto-reload:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

El backend estará disponible en:
- **API Base**: `http://localhost:8000/`
- **Documentación Swagger / OpenAPI**: `http://localhost:8000/docs`
- **Documentación ReDoc**: `http://localhost:8000/redoc`

---

## 🧪 Ejecución de Tests Unitarios

Para ejecutar las pruebas unitarias aisladas de extrusión 3D y fórmulas normativas SPDA:

```bash
pytest tests/ -v
```

---

## 📖 Historias de Usuario Implementadas

### HU02 — Cargar plano de la edificación
- `POST /api/v1/planos` — Recibe archivo `.dxf` o `.pdf` vía `UploadFile` e `idProyecto`. Valida extensión, integridad DXF con `ezdxf` y guarda metadatos + modelo 2D.
- `GET /api/v1/planos/{id}/preview` — Devuelve entidades geométricas 2D del plano interpretado.

### HU03 — Crear y visualizar modelo en 3D (extrusión geométrica determinística)
- `POST /api/v1/modelos3d` — Dispara la extrusión 3D a partir de un `idModelo2D`. Extruye prismas verticales e interpola elevación Z de techos inclinados con `numpy`.
- `GET /api/v1/modelos3d/{id}` — Devuelve geometría 3D estructurada (`positions`, `indices`) compatible con `THREE.BufferGeometry`.
- `PATCH /api/v1/modelos3d/{id}/reset-view` — Restablece los parámetros de cámara y objetivo por defecto.

### HU04 — Calcular nivel de riesgo SPDA
- `POST /api/v1/niveles-proteccion` — Recibe dimensiones, ubicación y factores de la edificación. Calcula $A_e$, $N_d$, $N_c$ y evalúa necesidad de SPCR y nivel I..IV según IEC 62305 / IRAM 2184.
- `GET /api/v1/niveles-proteccion/{idProyecto}` — Devuelve el cálculo de riesgo guardado.

### HU05 — Posicionar dispositivos captores y verificar cobertura
- `POST /api/v1/mastiles` — Agrega un mástil captor (coordenadas, altura, tipo).
- `PUT /api/v1/mastiles/{id}` — Mueve o actualiza un mástil captor.
- `DELETE /api/v1/mastiles/{id}` — Elimina un mástil captor.
- `GET /api/v1/mastiles/proyecto/{idProyecto}/cobertura` — Valida la cobertura en 3D mediante el **Método de la Esfera Rodante** y devuelve los puntos protegidos y desprotegidos.
