# Desarrollo y despliegue en Jetson Nano con Python 3.9

Este documento describe los pasos recomendados para clonar el repositorio, crear el entorno virtual con Python 3.9, instalar dependencias y ejecutar la aplicación en una Jetson Nano. Así podrás desarrollar y probar todo en el entorno real de producción.

---

## 1. Acceso y preparación del entorno

1. **Accede a la Jetson Nano por SSH**  
   Puedes usar VS Code con la extensión "Remote - SSH" o cualquier cliente SSH:
   ```bash
   ssh <usuario>@<ip_jetson>
   ```

2. **Instala Python 3.9 (si no está instalado)**
   ```bash
   sudo apt update
   sudo apt install python3.9 python3.9-venv python3.9-dev
   ```

3. **Clona el repositorio**
   ```bash
   git clone https://github.com/Denniels/iot_streamlit.git
   cd iot_streamlit/iot_streamlit
   ```

---

## 2. Crear y activar el entorno virtual

1. **Crea el entorno virtual con Python 3.9**
   ```bash
   python3.9 -m venv .iot_streamlit
   ```

2. **Activa el entorno virtual**
   ```bash
   source .iot_streamlit/bin/activate
   ```

3. **Instala las dependencias**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## 3. Configuración de variables de entorno

Asegúrate de tener configuradas las variables de entorno necesarias para la conexión a la base de datos y otros servicios. Puedes usar un archivo `.env` o exportarlas manualmente.

---

## 4. Ejecución y pruebas locales

1. **Ejecuta la aplicación backend**
   ```bash
   python main.py
   ```
   o si usas una API RESTful:
   ```bash
   uvicorn api:app --host 0.0.0.0 --port 8000
   ```

2. **Verifica que la Jetson Nano detecta los dispositivos conectados (USB, Ethernet, etc.) y que los datos se envían correctamente a Supabase y/o la API RESTful.**

---

## 5. (Opcional) Uso de Docker

Si prefieres usar Docker, sigue estos pasos:

1. **Construye la imagen**
   ```bash
   docker build -t iot_backend ./backend
   ```

2. **Ejecuta el contenedor**
   ```bash
   docker run --rm -it --network host --device /dev/ttyUSB0 \
     -e DB_HOST=<host_db> -e DB_USER=<usuario> -e DB_PASS=<password> -e DB_NAME=<nombre_db> \
     iot_backend
   ```
   > Ajusta el nombre del dispositivo USB si es necesario (por ejemplo, `/dev/ttyACM0`).

---

## 6. Acceso al frontend y backend

- **Backend:**  
  Si el backend expone una API HTTP, accede desde cualquier dispositivo en la red local usando la IP de la Jetson Nano y el puerto configurado (por ejemplo, `http://<IP_JETSON>:8000`).

- **Frontend (Streamlit):**  
  Si decides ejecutar el frontend en la Jetson Nano, expón el puerto 8501:
  ```bash
  docker run --rm -it -p 8501:8501 iot_frontend
  ```
  Accede desde un navegador en la red local a `http://<IP_JETSON>:8501`.  
  Si el frontend está desplegado en Streamlit Community Cloud, accede mediante la URL pública proporcionada por Streamlit.

---

## 7. Consejos de desarrollo

- Trabajar directamente en la Jetson Nano evita problemas de compatibilidad y asegura que todo funcione en el entorno real.
- Puedes usar VS Code vía SSH para editar, probar y depurar el código cómodamente.
- Siempre usa el entorno virtual `.iot_streamlit` con Python 3.9 para máxima compatibilidad.

---

Para más detalles sobre la estructura y funcionamiento general, consulta el archivo principal `README.md`.
