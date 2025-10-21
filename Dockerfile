# Dockerfile para el backend IoT en Jetson Nano
FROM nvcr.io/nvidia/l4t-ml:r32.7.1-py3

# Información del mantenedor
LABEL maintainer="IoT Streamlit Backend"
LABEL description="Backend IoT para detección de dispositivos Arduino y Modbus en Jetson Nano"

# Variables de entorno
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    build-essential \
    pkg-config \
    libhdf5-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg8-dev \
    liblapack-dev \
    libblas-dev \
    gfortran \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar archivos de requirements
COPY requirements_local.txt .
COPY requirements_cloud.txt .

# Instalar dependencias Python
RUN pip3 install --no-cache-dir --upgrade pip
RUN pip3 install --no-cache-dir -r requirements_local.txt

# Copiar código de la aplicación
COPY backend/ ./backend/
COPY database/ ./database/
COPY main.py .
COPY .env.local .env

# Crear directorio para logs
RUN mkdir -p logs

# Exponer puerto de la API
EXPOSE 8000

# Comando por defecto
CMD ["python3", "main.py", "--mode", "full", "--interval", "10"]
