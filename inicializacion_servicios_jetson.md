# Guia para inicializar los servicios en el host del backend, que en mi caso es un Jetson Nano
>

## Detén todos los servicios relacionados
sudo systemctl stop acquire_data.service
sudo systemctl stop backend_api.service
sudo systemctl stop sync_local_db.service
sudo systemctl stop start_cloudflare_py.service

## Sal del entorno virtual si está activo
deactivate

## Reactiva el entorno virtual
source /home/daniel/repos/iot_streamlit/.iot_streamlit/bin/activate

## (Opcional) Instala dependencias si hiciste cambios en requirements.txt
pip install -r requirements.txt

## Reinicia los servicios
sudo systemctl start acquire_data.service
sudo systemctl start backend_api.service
sudo systemctl start sync_local_db.service
sudo systemctl start start_cloudflare_py.service