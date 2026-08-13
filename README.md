# FARADYNE — Platforma de Diseño y Simulación SPDA

**FARADYNE** es una plataforma profesional de diseño, análisis y cálculo de Sistemas de Protección contra Descargas Atmosféricas (SPDA) en cumplimiento estricto con las normativas **AEA 92305** e **IEC 62305**.

---

## 🏗 Arquitectura General

El sistema está estructurado mediante **Clean Architecture**, **DDD (Domain-Driven Design)** y los principios **SOLID**, garantizando un alto desacoplamiento entre el núcleo de cálculo, las representaciones interactivas (Modelo2D y Modelo3D) y los motores de importación/exportación de archivos CAD (DXF, STEP, OBJ, STL).

- **Frontend (SPA Web / Three.js)**: Interfaz interactiva para importación CAD 2D/3D, edición visual de captadores, bajadas y mallas a tierra, y visualización en tiempo real con WebGL.
- **Backend (FastAPI)**: API RESTful asíncrona de alto rendimiento que expone servicios de procesamiento geométrico, cálculos de volumen de protección (Método de la Esfera Rodante / Ángulo de Protección) y gestión de proyectos.
- **Base de Datos (PostgreSQL + PostGIS)**: Persistencia relacional y geoespacial para la gestión de usuarios, auditoría, versiones del Modelo2D/3D y metadatos de proyectos SPDA.
- **Contenedorización (Docker & Nginx)**: Entorno aislado y reproducible tanto para desarrollo local con *live-reload* como para despliegue productivo con proxy inverso y SSL.

---

## 🛠 Stack Tecnológico

| Capa | Tecnologías |
| :--- | :--- |
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic v2, ezdxf, Shapely, PyGSLIB / SciPy |
| **Frontend** | Node.js 20+, React 18, TypeScript, Vite, Three.js / React Three Fiber, Tailwind CSS |
| **Base de Datos** | PostgreSQL 15, Extensiones PostGIS y uuid-ossp |
| **Infraestructura** | Docker, Docker Compose, Nginx Alpine |

---

## 📋 Requisitos Previos

- **Docker** 24.0+ y **Docker Compose** 2.20+
- **Python** 3.11+ (para desarrollo local sin Docker)
- **Node.js** 20+ y **npm** 10+ (para desarrollo local sin Docker)

---

## 🚀 Inicio Rápido (Docker)

Para levantar la infraestructura completa en modo desarrollo:

```bash
# 1. Clonar el repositorio y copiar variables de entorno
cp .env.example .env

# 2. Levantar todos los servicios con Docker Compose
docker-compose up --build
```

### 🌐 URLs de Desarrollo

- **Frontend App**: [http://localhost:5173](http://localhost:5173)
- **Backend REST API**: [http://localhost:8000](http://localhost:8000)
- **Documentación OpenAPI (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Documentación ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 💻 Desarrollo Local (Sin Docker)

### 1. Backend

```bash
cd backend
python -m venv .venv
# En Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# En Linux/macOS:
# source .venv/bin/activate

pip install -r requirements-dev.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## 📁 Estructura del Proyecto

```
FARADYNE/
├── backend/                  # Código fuente del backend FastAPI
│   ├── app/                  # Módulos principales (Core, Domain, Use Cases, Interfaces)
│   ├── tests/                # Suite de pruebas unitarias e integración
│   └── main.py               # Punto de entrada FastAPI
├── frontend/                 # Código fuente del frontend React + Vite
│   ├── src/                  # Componentes, hooks, visores 3D/2D
│   └── package.json
├── docker/                   # Dockerfiles y scripts de inicialización
│   ├── backend/              # Dockerfile de backend
│   ├── frontend/             # Dockerfile de frontend
│   └── postgres/             # init.sql y configuraciones DB
├── nginx/                    # Configuración de Nginx para producción
├── .env.example              # Plantilla de variables de entorno
├── .gitignore                # Reglas de exclusión de Git
├── docker-compose.yml        # Orquestación de desarrollo
├── docker-compose.prod.yml   # Orquestación de producción
└── README.md                 # Documentación principal del proyecto
```

---

## 📏 Convenciones de Nombres

- **Archivos Python**: `snake_case.py` (ej. `mesh_calculator.py`)
- **Clases Python / TypeScript**: `PascalCase` (ej. `SphereRollingService`, `ProjectRepository`)
- **Variables y Funciones**: `snake_case` (Python), `camelCase` (TypeScript/JS)
- **Componentes React**: `PascalCase.tsx` (ej. `Viewer3D.tsx`)
- **Commits Git**: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`

---

## 🤝 Contribución

1. Crear una rama de característica (*feature branch*): `git checkout -b feature/nueva-funcionalidad`
2. Asegurarse de seguir los estándares PEP8 para Python y ESLint/Prettier para TypeScript.
3. Ejecutar los tests antes de realizar el PR.
4. Crear un Pull Request detallando los cambios introducidos.
