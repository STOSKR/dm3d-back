from fastapi import FastAPI, HTTPException, BackgroundTasks, File, UploadFile, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from cadquery.vis import show
import cadquery as cq
from stl import mesh
import os
import shutil
import uuid
import math
from typing import Optional
from datetime import datetime
import cv2
import numpy as np
from PIL import Image
import io
from scipy.spatial import Delaunay
import json

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

class ParametrosEstrella(BaseModel):
    n_tips: int  # Número de puntas de la estrella
    r_star: float  # Radio exterior de la estrella
    r2_star: float  # Radio interior de la estrella
    deep: float  # Profundidad del molde

class ParametrosImagen(BaseModel):
    umbral_min: Optional[int] = 60
    umbral_max: Optional[int] = 160
    porcentaje_contornos: Optional[float] = 0.0
    factor_simplificacion: Optional[float] = 1.0
    altura_molde: Optional[float] = 3.0
    grosor_base: Optional[float] = 1.0

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

        # Exporta el modelo a STL
        cq.exporters.export(umbrella, stl_path)

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
        
        # Exporta el modelo a STL
        cq.exporters.export(internal_hole, stl_path)
        
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
        
        # Exporta el modelo a STL
        cq.exporters.export(internal_hole, stl_path)
        
        # Captura de pantalla
        screenshot_path = os.path.join(OUTPUT_DIR, "triangle.png")
        show(internal_hole, width=800, height=800, screenshot=screenshot_path, zoom=2, row=0, elevation=-30, interact=False)
        
    except Exception as e:
        import traceback
        print(f"Error detallado en crear_modelo_triangulo: {str(e)}")
        print("Rastreo completo del error:")
        traceback.print_exc()
        raise e

def crear_modelo_estrella(params: ParametrosEstrella, stl_path: str):
    try:
        print("Iniciando creación de la estrella con los siguientes parámetros:")
        print(f"n_tips: {params.n_tips}, r_star: {params.r_star}, r2_star: {params.r2_star}, deep: {params.deep}")
        
        # Extraer parámetros
        n_tips = params.n_tips
        r_star = params.r_star
        r2_star = params.r2_star
        deep = params.deep
        
        print("Calculando puntos exteriores de la estrella...")
        # Calculo de puntos exteriores
        ex_points = []
        for i in range(n_tips):
            angle = 2 * math.pi * i / n_tips
            x = r_star * math.cos(angle)
            y = r_star * math.sin(angle)
            ex_points.append((x, y))
            print(f"  Punto exterior {i+1}: ({x:.2f}, {y:.2f})")

        print("Calculando puntos interiores de la estrella...")
        # Calculo de puntos interiores
        in_points = []
        gap = 2 * math.pi / (n_tips * 2)
        for i in range(n_tips):
            angle = (2 * math.pi * i / n_tips) - gap
            x = r2_star * math.cos(angle)
            y = r2_star * math.sin(angle)
            in_points.append((x, y))
            print(f"  Punto interior {i+1}: ({x:.2f}, {y:.2f})")

        print("Combinando puntos para formar la estrella...")
        points = []
        for i in range(n_tips):
            points.append(in_points[i])
            points.append(ex_points[i])
        print(f"  Total de puntos combinados: {len(points)}")

        print("Creando sketch con los puntos...")
        try:
            sk = cq.Sketch().polygon(points)
            print("  Sketch creado correctamente")
        except Exception as e:
            print(f"  ERROR al crear sketch: {str(e)}")
            raise

        print("Extruyendo sketch para crear sólido 3D...")
        try:
            solid = cq.Workplane("XY").placeSketch(sk).extrude(deep)
            print("  Extrusión completada correctamente")
        except Exception as e:
            print(f"  ERROR en extrusión: {str(e)}")
            raise

        print("Generando molde (shell)...")
        try:
            internal_hole = solid.faces(">Z").shell(-deep*0.1)
            print("  Molde generado correctamente")
        except Exception as e:
            print(f"  ERROR al generar molde: {str(e)}")
            raise

        print(f"Exportando modelo a STL: {stl_path}")
        try:
            cq.exporters.export(internal_hole, stl_path)
            print("  Exportación STL completada")
        except Exception as e:
            print(f"  ERROR al exportar STL: {str(e)}")
            raise
        
        print("Generando captura de pantalla...")
        # Captura de pantalla
        screenshot_path = os.path.join(OUTPUT_DIR, "star.png")
        try:
            # Intentar usar un método alternativo si show() falla
            try:
                show(internal_hole, width=800, height=800, screenshot=screenshot_path, zoom=2, row=0, elevation=-30, interact=False)
                print(f"  Captura guardada en: {screenshot_path}")
            except Exception as e1:
                print(f"  Error con método show(): {str(e1)}")
                guardar_captura_modelo(internal_hole, screenshot_path)
        except Exception as e:
            print(f"  ERROR al generar captura: {str(e)}")
            # No elevamos esta excepción ya que la captura no es crítica
        
        print("Modelo de estrella generado exitosamente")
        return True
        
    except Exception as e:
        import traceback
        print(f"ERROR FATAL en crear_modelo_estrella: {str(e)}")
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

@app.post("/generar-estrella/", summary="Genera un modelo 3D de estrella")
async def generar_estrella(parametros: ParametrosEstrella, background_tasks: BackgroundTasks):
    # Crear un ID único para este modelo
    stl_path = os.path.join(OUTPUT_DIR, f"star_{datetime.now().strftime('%d_%H%M%S')}.stl")

    try:
        print("Iniciando creación de la estrella...")
        # Crear el modelo 3D usando los parámetros proporcionados
        crear_modelo_estrella(parametros, stl_path)
        
        # Configurar eliminación del archivo después de 1 hora
        background_tasks.add_task(eliminar_archivo, stl_path, 3600)
        
        # Devolver directamente el archivo STL
        return FileResponse(
            path=stl_path,
            filename="estrella.stl",
            media_type="application/octet-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar el modelo: {str(e)}")

@app.post("/generar-molde-imagen/", summary="Genera un modelo 3D a partir de una imagen")
async def generar_molde_imagen(
    image: UploadFile = File(...),
    parametros: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = None
):
    # Parsear los parámetros JSON si existen
    params_obj = ParametrosImagen()
    if parametros:
        try:
            params_dict = json.loads(parametros)
            params_obj = ParametrosImagen(**params_dict)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Error al decodificar los parámetros JSON")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error en los parámetros: {str(e)}")
    
    try:
        # Leer la imagen
        contents = await image.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise HTTPException(status_code=400, detail="No se pudo leer la imagen")
        
        # Procesar la imagen
        img_blur = preprocesar_imagen(img)
        bordes = detectar_bordes(img_blur, params_obj.umbral_min, params_obj.umbral_max)
        contornos = encontrar_contornos(bordes)
        
        if not contornos:
            raise HTTPException(status_code=400, detail="No se encontraron contornos en la imagen")
        
        # Seleccionar contornos según el porcentaje
        cantidad_a_usar = max(1, int((params_obj.porcentaje_contornos / 100.0) * len(contornos)))
        contornos_seleccionados = contornos[:cantidad_a_usar]
        contorno_combinado = np.vstack(contornos_seleccionados)
        
        # Simplificar contorno
        contorno_simplificado = simplificar_contorno(contorno_combinado, params_obj.factor_simplificacion)
        
        # Crear archivo STL
        stl_path = os.path.join(OUTPUT_DIR, f"molde_{datetime.now().strftime('%d_%H%M%S')}.stl")
        crear_molde_stl(contorno_simplificado, stl_path, params_obj.altura_molde, params_obj.grosor_base)
        
        # Configurar eliminación del archivo después de 1 hora
        background_tasks.add_task(eliminar_archivo, stl_path, 3600)
        
        return FileResponse(
            path=stl_path,
            filename="molde.stl",
            media_type="application/octet-stream"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar la imagen: {str(e)}")

@app.get("/", summary="Ruta principal")
async def raiz():
    return {
        "mensaje": "API de Modelo 3D de Figuras",
        "descripción": "Use los endpoints para crear modelos 3D",
        "endpoints": [
            "/generar-paraguas/",
            "/generar-circulo/",
            "/generar-triangulo/",
            "/generar-estrella/",
            "/generar-molde-imagen/"
        ],
        "documentación": "/docs"
    }

def preprocesar_imagen(img):
    # Convertir a escala de grises
    img_gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Aplicar desenfoque gaussiano para reducir ruido
    img_blur = cv2.GaussianBlur(img_gris, (5, 5), 0)
    return img_blur

def detectar_bordes(img_blur, umbral_min=50, umbral_max=150):
    bordes = cv2.Canny(img_blur, umbral_min, umbral_max)
    kernel = np.ones((3, 3), np.uint8)
    bordes_dilatados = cv2.dilate(bordes, kernel, iterations=1)
    return bordes_dilatados

def encontrar_contornos(bordes):
    contornos, _ = cv2.findContours(bordes, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    contornos2 = sorted(contornos, key=cv2.contourArea, reverse=True)
    return contornos2

def simplificar_contorno(contorno, epsilon=1.0):
    return cv2.approxPolyDP(contorno, epsilon, True)

def crear_molde_stl(contorno, stl_path, altura_molde=10, grosor_base=2):
    puntos = contorno.reshape(-1, 2).astype(float)
    
    # Calcular centro y centrar puntos
    centro_x = np.mean(puntos[:, 0])
    centro_y = np.mean(puntos[:, 1])
    puntos[:, 0] -= centro_x
    puntos[:, 1] -= centro_y
    
    # Escalar los puntos
    factor_escala = 50.0 / max(np.max(puntos[:, 0]) - np.min(puntos[:, 0]),
                              np.max(puntos[:, 1]) - np.min(puntos[:, 1]))
    puntos *= factor_escala
    
    # Calcular dimensiones del molde
    x_min, y_min = np.min(puntos, axis=0)
    x_max, y_max = np.max(puntos, axis=0)
    
    # Añadir margen
    margen = 5
    x_min -= margen
    y_min -= margen
    x_max += margen
    y_max += margen
    
    # Crear vértices para la base
    vertices_base = [
        [x_min, y_min, 0],
        [x_max, y_min, 0],
        [x_max, y_max, 0],
        [x_min, y_max, 0],
        [x_min, y_min, grosor_base],
        [x_max, y_min, grosor_base],
        [x_max, y_max, grosor_base],
        [x_min, y_max, grosor_base],
    ]
    
    # Crear la forma del cortador
    num_puntos = len(puntos)
    vertices_cortador_inferior = []
    for x, y in puntos:
        vertices_cortador_inferior.append([x, y, grosor_base])
    vertices_cortador_inferior.append([0, 0, grosor_base])
    
    # Triangulación
    puntos_con_centro = np.vstack([puntos, [0, 0]])
    tri = Delaunay(puntos_con_centro[:, :2])
    
    caras_cortador_inferior = []
    for simplex in tri.simplices:
        caras_cortador_inferior.append([8 + simplex[2], 8 + simplex[1], 8 + simplex[0]])
    
    # Vértices laterales
    vertices_cortador_lateral = []
    for x, y in puntos:
        vertices_cortador_lateral.append([x, y, grosor_base + altura_molde])
    
    # Caras laterales
    caras_cortador_lateral = []
    for i in range(num_puntos):
        idx_inf_actual = 8 + i
        idx_inf_siguiente = 8 + ((i + 1) % num_puntos)
        idx_sup_actual = 8 + num_puntos + 1 + i
        idx_sup_siguiente = 8 + num_puntos + 1 + ((i + 1) % num_puntos)
        
        caras_cortador_lateral.append([idx_inf_actual, idx_sup_actual, idx_sup_siguiente])
        caras_cortador_lateral.append([idx_inf_actual, idx_sup_siguiente, idx_inf_siguiente])
    
    # Combinar vértices y caras
    todos_vertices = vertices_base + vertices_cortador_inferior + vertices_cortador_lateral
    todas_caras = caras_cortador_inferior + caras_cortador_lateral
    
    # Crear y guardar la malla
    molde = mesh.Mesh(np.zeros(len(todas_caras), dtype=mesh.Mesh.dtype))
    for i, (v1, v2, v3) in enumerate(todas_caras):
        molde.vectors[i] = np.array([
            todos_vertices[v1],
            todos_vertices[v2],
            todos_vertices[v3]
        ])
    
    molde.save(stl_path)

if __name__ == "__main__":
    import uvicorn
    import traceback
    
    
    # Generar el modelo 3D con los parámetros proporcionados
    modelo_id = str(uuid.uuid4())
    stl_path = os.path.join(OUTPUT_DIR, f"umbrella_{datetime.now().strftime('%d_%H_%M_%S')}.stl")
    
    # Iniciar el servidor
    puerto = 8080  # Cambiado de 8000 a 8080
    print(f"\nIniciando servidor en http://localhost:{puerto}")
    print("Puede probar la API usando Postman con los siguientes endpoints:")
    print(f"POST http://localhost:{puerto}/generar-paraguas/")
    print(f"POST http://localhost:{puerto}/generar-circulo/")
    print(f"POST http://localhost:{puerto}/generar-triangulo/")
    print(f"POST http://localhost:{puerto}/generar-estrella/")
    print(f"POST http://localhost:{puerto}/generar-molde-imagen/")
    print(f"GET http://localhost:{puerto}/docs para ver la documentación completa")
    
    try:
        uvicorn.run(app, host="0.0.0.0", port=puerto)
    except Exception as e:
        print(f"Error al iniciar el servidor: {str(e)}")
        traceback.print_exc() 