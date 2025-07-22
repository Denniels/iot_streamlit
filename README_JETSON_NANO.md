# Despliegue en Jetson Nano

Este documento describe los pasos para clonar el repositorio y ejecutar la aplicación en una Jetson Nano, permitiendo que el backend comience a funcionar y detectar dispositivos automáticamente.

## Pasos para el despliegue

1. **Clonar el repositorio**

```bash
git clone https://github.com/Denniels/iot_streamlit.git
cd iot_streamlit/iot_streamlit
```

2. **(Opcional) Configurar variables de entorno**

Asegúrate de tener configuradas las variables de entorno necesarias para la conexión a la base de datos y otros servicios.

3. **Construir y ejecutar el contenedor Docker**

```bash
docker build -t iot_backend ./backend
# Conecta el Arduino USB y asegúrate de que el Arduino Ethernet esté en la misma red
# Ejecuta el contenedor, agregando los permisos necesarios para el puerto USB:
docker run --rm -it --network host --device /dev/ttyUSB0 iot_backend
```

> Ajusta el nombre del dispositivo USB si es necesario (por ejemplo, `/dev/ttyACM0`).

4. **Verifica el funcionamiento**

- El backend comenzará a detectar y adquirir datos de los Arduinos y otros dispositivos en la red automáticamente.
- Los datos se enviarán a la base de datos y estarán disponibles para el frontend.

---

Para más detalles sobre la estructura y funcionamiento general, consulta el archivo principal `README.md`.
