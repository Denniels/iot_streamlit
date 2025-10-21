# Guia para inicializar los servicios en el host del backend, que en mi caso es un Jetson Nano
>

## Detén todos los servicios relacionados
```bash
sudo systemctl stop acquire_data.service
sudo systemctl stop backend_api.service
sudo systemctl stop sync_local_db.service
sudo systemctl stop start_cloudflare_resilient.service
```

## Sal del entorno virtual si está activo
```bash
deactivate
```
## Reactiva el entorno virtual
```bash
source /home/daniel/repos/iot_streamlit/.iot_streamlit/bin/activate
```

## (Opcional) Instala dependencias si hiciste cambios en requirements.txt
```bash
pip install -r requirements.txt
```
## Revisa el estado de los servicios
```bash
sudo systemctl status acquire_data.service
sudo systemctl status backend_api.service
sudo systemctl status sync_local_db.service
sudo systemctl status start_cloudflare_resilient.service
```
## Reinicia los servicios
```bash
sudo systemctl start acquire_data.service
sudo systemctl start backend_api.service
sudo systemctl start sync_local_db.service
sudo systemctl start start_cloudflare_resilient.service
```