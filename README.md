# API de Modelos 3D de Figuras

Esta API permite generar modelos 3D de diferentes figuras (paraguas, círculos, triángulos y estrellas) basados en parámetros personalizables, así como crear moldes 3D a partir de imágenes.

## Requisitos

### Instalación de dependencias básicas
```
pip install -r requirements.txt
```

### Instalación de CadQuery (necesario)
CadQuery y sus dependencias son difíciles de instalar con pip. Se recomienda usar conda:

```
conda install -c conda-forge -c cadquery cadquery=2.3.0
```

Alternativamente, puedes usar un entorno Docker que ya tiene todas las dependencias instaladas.

## Ejecución

Para iniciar el servidor:

```
python main.py
```

O alternativamente:

```
uvicorn main:app --reload
```

La API estará disponible en `http://localhost:8080`.

## Documentación

La documentación interactiva está disponible en `http://localhost:8080/docs`.

## Endpoints

### Generar un modelo 3D de Paraguas

**POST** `/generar-paraguas/`

Cuerpo de la solicitud (JSON):

```json
{
  "w_stick": 1.0,     // Ancho del palo del paraguas
  "r_bottom": 5.0,    // Radio de la parte inferior redondeada
  "h_stick": 20.0,    // Altura del palo
  "r_cano": 15.0,     // Radio del dosel
  "n_arcs": 8,        // Número de arcos
  "h_tail": 5.0,      // Altura de la cola
  "h_top": 3.0,       // Altura superior
  "deep": 2.0         // Profundidad del molde
}
```

### Generar un modelo 3D de Círculo

**POST** `/generar-circulo/`

Cuerpo de la solicitud (JSON):

```json
{
  "r_circle": 10.0,   // Radio del círculo
  "deep": 2.0         // Profundidad del molde
}
```

### Generar un modelo 3D de Triángulo

**POST** `/generar-triangulo/`

Cuerpo de la solicitud (JSON):

```json
{
  "side_length": 20.0, // Longitud del lado del triángulo
  "deep": 2.0          // Profundidad del molde
}
```

### Generar un modelo 3D de Estrella

**POST** `/generar-estrella/`

Cuerpo de la solicitud (JSON):

```json
{
  "n_tips": 5,        // Número de puntas de la estrella
  "r_star": 15.0,     // Radio exterior de la estrella
  "r2_star": 7.0,     // Radio interior de la estrella
  "deep": 2.0         // Profundidad del molde
}
```

### Generar un modelo 3D a partir de una imagen

**POST** `/generar-molde-imagen/`

Cuerpo de la solicitud (multipart/form-data):

- `file`: Archivo de imagen (jpg, png, avif, etc.)
- `umbral_min`: (opcional) Umbral mínimo para detección de bordes (default: 50)
- `umbral_max`: (opcional) Umbral máximo para detección de bordes (default: 150)
- `porcentaje_contornos`: (opcional) Porcentaje de contornos a usar (default: 10.0)
- `factor_simplificacion`: (opcional) Factor de simplificación del contorno (default: 1.0)
- `altura_molde`: (opcional) Altura del molde en mm (default: 10.0)
- `grosor_base`: (opcional) Grosor de la base en mm (default: 2.0)

Respuesta:
```json
{
  "mensaje": "Modelo 3D generado con éxito",
  "id_modelo": "identificador-único",
  "url_descarga": "/descargar-modelo/identificador-único"
}
```

### Descargar un modelo generado

**GET** `/descargar-modelo/{id_modelo}`

Retorna el archivo STL del modelo generado.

## Notas

- Los archivos generados se eliminan automáticamente después de 1 hora.
- Los modelos se guardan en el directorio `modelos_generados`. 