from typing import Any, Dict, List, Optional
from app.core.database import execute_query, fetch_all, fetch_one, serialize_json


class ProyectoRepository:

    @staticmethod
    def get_proyecto_by_id(id_proyecto: str) -> Optional[Dict[str, Any]]:
        """Fetch de la fila completa de 'proyecto' por su PK real (id_proyecto)."""
        query = "SELECT * FROM proyecto WHERE id_proyecto = %s;"
        return fetch_one(query, (id_proyecto,))
 
    @staticmethod
    def get_ubicacion_by_proyecto_id(id_proyecto: str) -> Optional[Dict[str, Any]]:
        """Trae solo id_proyecto/nombre/localidad del proyecto.
 
        Se usa para mostrar la localidad junto al Ng adoptado en el Paso 1
        del cálculo de Nivel de Protección (HU04), sin traer la fila entera.
        Es la misma columna ('localidad') que se matchea contra
        zona_ceraunica.ciudad para resolver el Ng (ver
        NivelProteccionRepository.get_zona_ceraunica_by_departamento).
        """
        query = """
            SELECT id_proyecto, nombre, localidad
            FROM proyecto
            WHERE id_proyecto = %s;
        """
        return fetch_one(query, (id_proyecto,))

    @staticmethod
    def list_proyectos() -> List[Dict[str, Any]]:
        """Devuelve todos los proyectos, ordenados por fecha de creación desc."""
        query = "SELECT * FROM proyecto ORDER BY fecha_creacion DESC;"
        return fetch_all(query) or []
    @staticmethod
    def create_proyecto(
        nombre: str,
        fecha_del_proyecto: str,  # Viene del formulario JSX
        cliente: Optional[str] = None,
        ubicacion: Optional[str] = None,
        descripcion: Optional[str] = None,
        departamento: Optional[str] = None,
        provincia: Optional[str] = None,
        localidad: Optional[str] = None,
        estado: str = "borrador",
    ) -> Dict[str, Any]:
        """Crea un nuevo proyecto en la tabla 'proyecto'."""
        
        # CURRENT_DATE se inyecta directamente en SQL, no como parámetro.
        query = """
            INSERT INTO proyecto (
                nombre, cliente, ubicacion, descripcion, 
                departamento, provincia, localidad, estado, 
                fecha_creacion, fecha_del_proyecto
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE, %s)
            RETURNING *;
        """
        
        params = (
            nombre, 
            cliente, 
            ubicacion, 
            descripcion, 
            departamento, 
            provincia, 
            localidad, 
            estado, 
            fecha_del_proyecto
        )
        
        try:
            resultado = execute_query(query, params, fetch=True)
            
            # Validaciones robustas para evitar el Error 500
            if isinstance(resultado, list) and len(resultado) > 0:
                return resultado[0]
            if isinstance(resultado, dict):
                return resultado
                
            return {}
            
        except Exception as e:
      
            print(" ERROR EN BASE DE DATOS AL CREAR PROYECTO:")
            print(e)
            raise e

    @staticmethod
    def update_proyecto(
        id_proyecto: str,
        nombre: Optional[str] = None,
        descripcion: Optional[str] = None,
        ubicacion: Optional[str] = None,
        departamento: Optional[str] = None,
        provincia: Optional[str] = None,
        localidad: Optional[str] = None,
        estado: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Actualiza los campos de un proyecto existente."""
        fields = []
        params = []

        if nombre is not None:
            fields.append("nombre = %s")
            params.append(nombre)
        if descripcion is not None:
            fields.append("descripcion = %s")
            params.append(descripcion)
        if ubicacion is not None:
            fields.append("ubicacion = %s")
            params.append(ubicacion)
        if departamento is not None:
            fields.append("departamento = %s")
            params.append(departamento)
        if provincia is not None:
            fields.append("provincia = %s")
            params.append(provincia)
        if localidad is not None:
            fields.append("localidad = %s")
            params.append(localidad)
        if estado is not None:
            fields.append("estado = %s")
            params.append(estado)

        if not fields:
            return ProyectoRepository.get_proyecto_by_id(id_proyecto)

        fields.append("fecha_actualizacion = NOW()")
        params.append(id_proyecto)
        query = f"UPDATE proyecto SET {', '.join(fields)} WHERE id = %s RETURNING *;"
        res = execute_query(query, tuple(params), fetch=True)
        return res if res else None