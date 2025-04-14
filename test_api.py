import requests
import json
import argparse

def main():
    # Configurar el parser de argumentos
    parser = argparse.ArgumentParser(description='Generar un modelo 3D de paraguas')
    parser.add_argument('--w_stick', type=float, default=2.0, help='Ancho del palo del paraguas')
    parser.add_argument('--r_bottom', type=float, default=5.0, help='Radio de la parte inferior redondeada')
    parser.add_argument('--h_stick', type=float, default=100.0, help='Altura del palo')
    parser.add_argument('--r_cano', type=float, default=50.0, help='Radio del dosel')
    parser.add_argument('--n_arcs', type=int, default=8, help='Número de arcos')
    parser.add_argument('--h_tail', type=float, default=20.0, help='Altura de la cola')
    parser.add_argument('--h_top', type=float, default=10.0, help='Altura superior')
    parser.add_argument('--deep', type=float, default=5.0, help='Profundidad del molde')
    
    # Parsear los argumentos
    args = parser.parse_args()
    
    # Crear el diccionario de parámetros
    parametros = {
        "w_stick": args.w_stick,
        "r_bottom": args.r_bottom,
        "h_stick": args.h_stick,
        "r_cano": args.r_cano,
        "n_arcs": args.n_arcs,
        "h_tail": args.h_tail,
        "h_top": args.h_top,
        "deep": args.deep
    }
    
    print("Enviando los siguientes parámetros:")
    print(json.dumps(parametros, indent=2))
    
    try:
        # Hacer la solicitud POST
        print("\nRealizando solicitud POST a http://localhost:8000/generar-paraguas/")
        response = requests.post("http://localhost:8000/generar-paraguas/", json=parametros)
        
        # Mostrar la respuesta completa
        print("\nRespuesta del servidor:")
        print(f"Código de estado: {response.status_code}")
        print(f"Headers: {response.headers}")
        print(f"Contenido: {response.text}")
        
        # Si la respuesta es exitosa, obtener el ID del modelo
        if response.status_code == 200:
            data = response.json()
            modelo_id = data.get("id_modelo")
            
            if modelo_id:
                print("\nID del modelo:", modelo_id)
                print("URL para descargar:", f"http://localhost:8000/descargar-modelo/{modelo_id}")
            else:
                print("No se encontró el ID del modelo en la respuesta")
        else:
            print(f"\nError: La solicitud falló con código {response.status_code}")
            if response.status_code == 422:
                print("Este es un error de validación. Los parámetros proporcionados no son válidos.")
    
    except Exception as e:
        print(f"Error al realizar la solicitud: {str(e)}")

if __name__ == "__main__":
    main() 