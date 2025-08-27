### borrar y limpiar registros de la bd al presentar conflictos en dispositivos, cortes de energia o relaciones corruptas

```powershell
bash -lc "export PGPASSWORD='DAms15820'; psql -h localhost -U iot_user -d iot_db -c 'DELETE FROM devices;' -P pager=off; psql -h localhost -U iot_user -d iot_db -c 'SELECT COUNT(*) FROM devices;' -P pager=off; sudo systemctl restart acquire_data.service; sleep 5; export PGPASSWORD='DAms15820'; psql -h localhost -U iot_user -d iot_db -c 'SELECT device_id, device_type, ip_address, port, status, updated_at FROM devices ORDER BY updated_at DESC LIMIT 20;' -P pager=off"
```
>
```powershell
bash -lc "sleep 10; export PGPASSWORD='DAms15820'; psql -h localhost -U iot_user -d iot_db -c 'SELECT device_id, device_type, ip_address, port, status, updated_at FROM devices ORDER BY updated_at DESC LIMIT 20;' -P pager=off"
```
>
```powershell
bash -lc "sleep 10; export PGPASSWORD='DAms15820'; psql -h localhost -U iot_user -d iot_db -c 'SELECT device_id, device_type, ip_address, port, status, updated_at FROM devices ORDER BY updated_at DESC LIMIT 20;' -P pager=off"
```
>
```powershell
bash -lc "sleep 10; export PGPASSWORD='DAms15820'; psql -h localhost -U iot_user -d iot_db -c 'SELECT device_id, device_type, ip_address, port, status, updated_at FROM devices ORDER BY updated_at DESC LIMIT 20;' -P pager=off"
```