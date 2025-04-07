FROM continuumio/miniconda3:latest

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    libglu1-mesa \
    libgl1-mesa-glx \
    libxrandr2 \
    libxinerama1 \
    libxcursor1 \
    libxi6 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos de requisitos
COPY requirements.txt .

# Instalar CadQuery con conda y otras dependencias con pip
RUN conda install -c conda-forge -c cadquery cadquery=2.3.0 && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el resto de los archivos
COPY . .

# Crear directorio para modelos generados
RUN mkdir -p modelos_generados

# Exponer puerto
EXPOSE 8000

# Comando para ejecutar la aplicación
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 