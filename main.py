from fastapi import FastAPI, HTTPException, BackgroundTasks, File, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from cadquery.vis import show
import cadquery as cq
from stl import mesh
import os
import shutil
import uuid
from typing import Optional
from datetime import datetime

app = FastAPI(
    title="API de Modelos 3D de Figuras",
    description="API para generar modelos 3D de figuras (paraguas, círculos, triángulos) basados en parámetros",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite cualquier origen
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos los métodos
    allow_headers=["*"],  # Permite todos los headers
)

# Directorio para almacenar archivos STL generados
OUTPUT_DIR = "modelos_generados"
os.makedirs(OUTPUT_DIR, exist_ok=True)

class ParametrosParaguas(BaseModel):
    w_stick: float  # Ancho del palo del paraguas
    r_bottom: float  # Radio de la parte inferior redondeada
    h_stick: float  # Altura del palo
    r_cano: float  # Radio del dosel
    n_arcs: int  # Número de arcos
    h_tail: float  # Altura de la cola
    h_top: float  # Altura superior
    deep: float  # Profundidad del molde

class ParametrosCirculo(BaseModel):
    r_circle: float  # Radio del círculo
    deep: float  # Profundidad del molde

class ParametrosTriangulo(BaseModel):
    base: float  # Base del triángulo
    height: float  # Altura del triángulo
    deep: float  # Profundidad del molde

def solicitar_parametros():
    print("\n=== Ingrese los parámetros del paraguas ===")
    parametros = {}
    
    parametros['h_top'] = float(input("Altura de Punta: "))
    parametros['r_cano'] = float(input("Radio superior: "))
    parametros['n_arcs'] = int(input("Arcos: "))
    parametros['h_stick'] = float(input("Longitud Mango: "))
    parametros['w_stick'] = float(input("Anchura Mango: "))
    parametros['r_bottom'] = float(input("Radio Mango: "))
    parametros['h_tail'] = float(input("Altura inferior: "))
    parametros['deep'] = float(input("Grosor: "))
    
    return ParametrosParaguas(**parametros)

@app.post("/generar-paraguas/", summary="Genera un modelo 3D de paraguas")
async def generar_paraguas(parametros: ParametrosParaguas, background_tasks: BackgroundTasks):
    # Crear un ID único para este modelo
    stl_path = os.path.join(OUTPUT_DIR, f"umbrella_{datetime.now().strftime('%d_%H%M%S')}.stl")
    
    try:
        # Crear el modelo 3D usando los parámetros proporcionados
        crear_modelo_paraguas(parametros, stl_path)
        
        # Configurar eliminación del archivo después de 1 hora
        background_tasks.add_task(eliminar_archivo, stl_path, 3600)
        
        # Devolver directamente el archivo STL
        return FileResponse(
            path=stl_path,
            filename="paraguas.stl",
            media_type="application/octet-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar el modelo: {str(e)}")

def eliminar_archivo(ruta: str, segundos: int):
    import time
    time.sleep(segundos)
    if os.path.exists(ruta):
        os.remove(ruta)

def guardar_captura_modelo(modelo, ruta_archivo):
    """Guarda una captura del modelo 3D usando VTK directamente"""
    try:
        from cadquery.vis import cad_display
        display = cad_display.CadDisplay(modelo)
        display._renderer.SaveImage(ruta_archivo)
        print(f"Captura guardada en: {ruta_archivo}")
        return True
    except Exception as e:
        print(f"Error al guardar captura: {str(e)}")
        return False

def crear_modelo_paraguas(params: ParametrosParaguas, stl_path: str):
    try:
        print("Iniciando creación del modelo con los siguientes parámetros:")
        print(f"w_stick: {params.w_stick}, r_bottom: {params.r_bottom}, h_stick: {params.h_stick}")
        print(f"r_cano: {params.r_cano}, n_arcs: {params.n_arcs}, h_tail: {params.h_tail}")
        print(f"h_top: {params.h_top}, deep: {params.deep}")
        
        # Extraer parámetros
        w_stick = params.w_stick
        r_bottom = params.r_bottom
        h_stick = params.h_stick
        r_cano = params.r_cano
        n_arcs = params.n_arcs
        h_tail = params.h_tail
        h_top = params.h_top
        deep = params.deep
        
        # Cálculos derivados
        print("Realizando cálculos derivados...")
        r_bottom2 = r_bottom - w_stick
        r_arcs = r_cano / n_arcs
        h_final_stick = h_stick + r_cano + h_top
        
        print(f"Valores calculados: r_bottom2: {r_bottom2}, r_arcs: {r_arcs}, h_final_stick: {h_final_stick}")
        
        # Verificar valores negativos o problemáticos
        if r_bottom2 <= 0:
            raise ValueError(f"El valor de r_bottom2 ({r_bottom2}) debe ser positivo. Ajuste los parámetros r_bottom y w_stick.")
        
        print("Creando parte 1 (mango)...")
        # Parte inferior del paraguas (mango)
        part1 = cq.Workplane("XY").box(w_stick, h_tail, deep).translate((r_bottom2+w_stick/2, h_tail/2, 0))
        
        print("Creando parte 2...")
        part2 = cq.Workplane("XY").box(w_stick, h_final_stick, deep).translate((-(w_stick+r_bottom2)+w_stick/2, h_final_stick/2, 0))
        
        print("Creando parte 3...")
        part3 = cq.Workplane("XY").cylinder(deep, w_stick/2).translate((w_stick/2+r_bottom2, h_tail, 0))

        print("Creando primer bloque de diferencia...")
        # Primer bloque de diferencia
        cutout1 = cq.Workplane("XY").box(r_bottom*2+2, r_bottom*2+2, deep+1).translate((0, (r_bottom*2+2)/2, -0.2))
        cutout2 = cq.Workplane("XY").cylinder(deep+1, r_bottom2).translate((0, 0, -0.2))
        main_diff = (
            cq.Workplane("XY")
            .cylinder(deep, r_bottom)
            .cut(cutout2)
            .cut(cutout1)
        )

        print("Creando segundo bloque de diferencia...")
        # Segundo bloque de diferencia
        large_cylinder = cq.Workplane("XY").cylinder(deep, r_cano).translate((0, h_stick, 0))
        small_cylinders = []
        new_center = -r_cano + r_arcs
        
        print(f"Creando {n_arcs} arcos...")
        for i in range(n_arcs):
            print(f"Creando arco {i+1} en posición {new_center}")
            small_cylinders.append(cq.Workplane("XY").cylinder(deep+1, r_arcs).translate((new_center, h_stick, -0.2)))
            new_center += r_arcs*2

        print("Aplicando recorte con cubo...")
        cutout_cube = cq.Workplane("XY").box(r_cano*2, h_stick*2+r_cano, deep+1).translate((0, -r_cano/2, -0.2))
        second_diff = large_cylinder.cut(cutout_cube)
        
        print("Aplicando recortes de cilindros pequeños...")
        for i, cyl in enumerate(small_cylinders):
            print(f"Recortando cilindro {i+1}")
            second_diff = second_diff.cut(cyl)
        
        print("Aplicando traslación...")
        second_diff = second_diff.translate((-(w_stick/2+r_bottom2), 0, 0))

        print("Combinando todas las partes...")
        # Cambio en la forma de unir las partes para evitar problemas con TopoDS_Solid
        # Método 1: Unir progresivamente
        umbrella = part1
        print("- Uniendo part1 + part2")
        umbrella = umbrella.union(part2)
        print("- Uniendo + part3")
        umbrella = umbrella.union(part3)
        print("- Uniendo + main_diff")
        umbrella = umbrella.union(main_diff)
        print("- Uniendo + second_diff")
        umbrella = umbrella.union(second_diff)
        
        print("Creando shell interno...")
        internal_hole = umbrella.faces(">Z").shell(-deep*0.1)
        umbrella = internal_hole

        print(f"Exportando modelo a {stl_path}...")
        # Exporta el modelo a STL
        cq.exporters.export(umbrella, stl_path)
        print("Exportación completada con éxito")

        # Método 1: Usar ruta absoluta para la captura de pantalla con show()
        screenshot_path = os.path.join(OUTPUT_DIR, "umbrella.png")
        show(umbrella, width=800, height=800, screenshot=screenshot_path, zoom=2, row=-20, elevation=-30, interact=False)
        print(f"Método 1: Intento guardar captura en: {screenshot_path}")
        
        # Método 2: Usar función alternativa de captura
        screenshot_path2 = os.path.join(OUTPUT_DIR, "umbrella_alt.png")
        guardar_captura_modelo(umbrella, screenshot_path2)
        
    except Exception as e:
        import traceback
        print(f"Error detallado en crear_modelo_paraguas: {str(e)}")
        print("Rastreo completo del error:")
        traceback.print_exc()
        raise e

def crear_modelo_circulo(params: ParametrosCirculo, stl_path: str):
    try:
        print("Iniciando creación del círculo con los siguientes parámetros:")
        print(f"r_circle: {params.r_circle}, deep: {params.deep}")
        
        # Extraer parámetros
        r_circle = params.r_circle
        deep = params.deep
        
        # Crear círculo
        part1 = cq.Workplane("XY").cylinder(deep, r_circle)
        
        # Generar el molde
        internal_hole = part1.faces(">Z").shell(-deep*0.1)
        
        print(f"Exportando modelo a {stl_path}...")
        # Exporta el modelo a STL
        cq.exporters.export(internal_hole, stl_path)
        print("Exportación completada con éxito")
        
        # Captura de pantalla
        screenshot_path = os.path.join(OUTPUT_DIR, "circle.png")
        show(internal_hole, width=800, height=800, screenshot=screenshot_path, zoom=2, row=0, elevation=-30, interact=False)
        
    except Exception as e:
        import traceback
        print(f"Error detallado en crear_modelo_circulo: {str(e)}")
        print("Rastreo completo del error:")
        traceback.print_exc()
        raise e

def crear_modelo_triangulo(params: ParametrosTriangulo, stl_path: str):
    try:
        print("Iniciando creación del triángulo con los siguientes parámetros:")
        print(f"base: {params.base}, height: {params.height}, deep: {params.deep}")
        
        # Extraer parámetros
        base = params.base
        height = params.height
        deep = params.deep
        
        # Crear triángulo
        # Definir los puntos para el triángulo equilátero
        points = [
            (-base/2, 0),
            (base/2, 0),
            (0, height)
        ]
        
        # Crear perfil del triángulo y extruirlo
        part1 = cq.Workplane("XY").polyline(points).close().extrude(deep)
        
        # Generar el molde
        internal_hole = part1.faces(">Z").shell(-deep*0.1)
        
        print(f"Exportando modelo a {stl_path}...")
        # Exporta el modelo a STL
        cq.exporters.export(internal_hole, stl_path)
        print("Exportación completada con éxito")
        
        # Captura de pantalla
        screenshot_path = os.path.join(OUTPUT_DIR, "triangle.png")
        show(internal_hole, width=800, height=800, screenshot=screenshot_path, zoom=2, row=0, elevation=-30, interact=False)
        
    except Exception as e:
        import traceback
        print(f"Error detallado en crear_modelo_triangulo: {str(e)}")
        print("Rastreo completo del error:")
        traceback.print_exc()
        raise e

@app.post("/generar-circulo/", summary="Genera un modelo 3D de círculo")
async def generar_circulo(parametros: ParametrosCirculo, background_tasks: BackgroundTasks):
    # Crear un ID único para este modelo
    stl_path = os.path.join(OUTPUT_DIR, f"circle_{datetime.now().strftime('%d_%H%M%S')}.stl")
    
    try:
        # Crear el modelo 3D usando los parámetros proporcionados
        crear_modelo_circulo(parametros, stl_path)
        
        # Configurar eliminación del archivo después de 1 hora
        background_tasks.add_task(eliminar_archivo, stl_path, 3600)
        
        # Devolver directamente el archivo STL
        return FileResponse(
            path=stl_path,
            filename="circulo.stl",
            media_type="application/octet-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar el modelo: {str(e)}")

@app.post("/generar-triangulo/", summary="Genera un modelo 3D de triángulo")
async def generar_triangulo(parametros: ParametrosTriangulo, background_tasks: BackgroundTasks):
    # Crear un ID único para este modelo
    stl_path = os.path.join(OUTPUT_DIR, f"triangle_{datetime.now().strftime('%d_%H%M%S')}.stl")
    
    try:
        # Crear el modelo 3D usando los parámetros proporcionados
        crear_modelo_triangulo(parametros, stl_path)
        
        # Configurar eliminación del archivo después de 1 hora
        background_tasks.add_task(eliminar_archivo, stl_path, 3600)
        
        # Devolver directamente el archivo STL
        return FileResponse(
            path=stl_path,
            filename="triangulo.stl",
            media_type="application/octet-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar el modelo: {str(e)}")

@app.get("/", summary="Ruta principal")
async def raiz():
    return {
        "mensaje": "API de Modelo 3D de Figuras",
        "descripción": "Use los endpoints para crear modelos 3D",
        "endpoints": [
            "/generar-paraguas/",
            "/generar-circulo/",
            "/generar-triangulo/"
        ],
        "documentación": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    import traceback
    
    
    # Generar el modelo 3D con los parámetros proporcionados
    modelo_id = str(uuid.uuid4())
    stl_path = os.path.join(OUTPUT_DIR, f"umbrella_{datetime.now().strftime('%d_%H_%M_%S')}.stl")
    
    try:
        # Crear el modelo 3D usando los parámetros proporcionados
        print("\nGenerando modelo 3D con los parámetros ingresados...")
        crear_modelo_paraguas(parametros, stl_path)
        print(f"Modelo generado con éxito: {stl_path}")
        print(f"ID del modelo: {modelo_id}")
        print(f"Puede descargar el modelo en: http://localhost:8000/descargar-modelo/{modelo_id}")
    except Exception as e:
        print(f"Error al generar el modelo: {str(e)}")
        print("Rastreo completo del error:")
        traceback.print_exc()
    
    # Iniciar el servidor
    print("\nIniciando servidor en http://localhost:8000")
    print("Puede probar la API usando Postman con los siguientes endpoints:")
    print("POST http://localhost:8000/generar-paraguas/")
    print("POST http://localhost:8000/generar-circulo/")
    print("POST http://localhost:8000/generar-triangulo/")
    print("GET http://localhost:8000/docs para ver la documentación completa")
    
    uvicorn.run(app, host="0.0.0.0", port=8000) 