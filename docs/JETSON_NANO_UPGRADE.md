# Actualización y preparación de Jetson Nano para desarrollo remoto con VS Code

Este documento describe cómo actualizar una Jetson Nano con Ubuntu 18.04 (L4T) a Ubuntu 20.04, instalar Python 3.9 y todas las dependencias necesarias para trabajar desde VS Code en tu PC usando SSH remoto.

---

## 1. Respaldo de archivos importantes
Antes de actualizar, guarda tus proyectos y configuraciones:
```bash
mkdir ~/respaldo
cp -r ~/iot_streamlit ~/respaldo/
# Agrega aquí cualquier otro archivo o carpeta importante
```

---

## 2. Actualización del sistema operativo a Ubuntu 20.04

1. **Actualiza todos los paquetes actuales**
   ```bash
   sudo apt update
   sudo apt upgrade -y
   sudo apt dist-upgrade -y
   sudo apt autoremove -y
   ```

2. **Instala el gestor de actualización**
   ```bash
   sudo apt install -y update-manager-core
   ```

3. **Permite la actualización de la distribución**
   Edita el archivo `/etc/update-manager/release-upgrades` y cambia la línea:
   ```
   Prompt=never
   ```
   por
   ```
   Prompt=normal
   ```

4. **Inicia la actualización de la distribución**
   ```bash
   sudo do-release-upgrade
   ```
   - Sigue las instrucciones en pantalla. El proceso puede tardar varias horas.
   - Si te pregunta por servicios o archivos de configuración, elige "mantener actual" salvo que tengas personalizaciones.

5. **Reinicia la Jetson Nano**
   ```bash
   sudo reboot
   ```

6. **Verifica la versión**
   ```bash
   lsb_release -a
   uname -m
   ```

---

## 3. Instalación de dependencias para desarrollo

Instala las herramientas necesarias para Python, VS Code Server y desarrollo general:
```bash
sudo apt update
sudo apt install -y build-essential python3.9 python3.9-venv python3.9-dev python3-pip git libssl-dev libffi-dev libstdc++6
```

---

## 4. Configuración de SSH para VS Code

1. **Verifica que el servicio SSH esté activo**
   ```bash
   sudo systemctl status ssh
   # Si no está activo:
   sudo systemctl enable ssh
   sudo systemctl start ssh
   ```

2. **Obtén la IP de la Jetson Nano**
   ```bash
   ip a
   # Busca la IP en wlan0 o eth0
   ```

3. **Conéctate desde VS Code en tu PC**
   - Instala la extensión "Remote - SSH" en VS Code.
   - Agrega la IP y usuario en tu archivo de configuración SSH (`~/.ssh/config`):
     ```
     Host jetson-nano
         HostName <IP_JETSON>
         User <usuario>
     ```
   - Conéctate usando la paleta de comandos de VS Code: `Remote-SSH: Connect to Host...`

---

## 5. Clona tu proyecto y prepara el entorno Python

1. **Clona el repositorio**
   ```bash
   git clone https://github.com/Denniels/iot_streamlit.git
   cd iot_streamlit/iot_streamlit
   ```

2. **Crea y activa el entorno virtual con Python 3.9**
   ```bash
   python3.9 -m venv .iot_streamlit
   source .iot_streamlit/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## 6. Consejos finales
- Si usas aceleración de GPU, revisa la compatibilidad de los drivers tras el upgrade.
- Trabaja siempre en el entorno virtual `.iot_streamlit`.
- Si tienes problemas con VS Code Server, verifica las versiones de glibc y libstdc++6.

---

Para dudas o problemas, consulta la documentación oficial de Jetson Nano y VS Code Remote SSH.
