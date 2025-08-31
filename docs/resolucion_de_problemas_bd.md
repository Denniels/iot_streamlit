### borrar y limpiar registros de la bd al presentar conflictos en dispositivos, cortes de energia o relaciones corruptas

Nota: los comandos descritos abajo son destructivos (eliminan filas). Antes de ejecutar cualquier borrado, realiza un backup completo de la base de datos:

- Hacer backup (dump):
  - exporta la contraseña y realiza un volcado comprimido:
    - export PGPASSWORD='DAms15820'  
    - pg_dump -h localhost -U iot_user -F c -b -v -f ~/iot_db_backup.dump iot_db

Explicación detallada línea por línea del bloque original

1) Comando concatenado original (ejecuta varias acciones en secuencia)
```
bash -lc "export PGPASSWORD='DAms15820'; psql -h localhost -U iot_user -d iot_db -c 'DELETE FROM devices;' -P pager=off; psql -h localhost -U iot_user -d iot_db -c 'SELECT COUNT(*) FROM devices;' -P pager=off; sudo systemctl restart acquire_data.service; sleep 5; export PGPASSWORD='DAms15820'; psql -h localhost -U iot_user -d iot_db -c 'SELECT device_id, device_type, ip_address, port, status, updated_at FROM devices ORDER BY updated_at DESC LIMIT 20;' -P pager=off"
```

- `bash -lc "..."`  
  - Ejecuta la cadena entre comillas con un shell (bash). Útil para encadenar varios comandos en una sola línea o dentro de scripts.

- `export PGPASSWORD='DAms15820'`  
  - Define la variable de entorno `PGPASSWORD` para que `psql` y otros clientes PostgreSQL puedan autenticarse sin prompt interactivo. (Es conveniente usar `.pgpass` para mayor seguridad.)

- `psql -h localhost -U iot_user -d iot_db -c 'DELETE FROM devices;' -P pager=off`  
  - `psql` es el cliente PostgreSQL.
  - `-h localhost` conecta al host local.
  - `-U iot_user` usa el usuario `iot_user`.
  - `-d iot_db` selecciona la base `iot_db`.
  - `-c 'DELETE FROM devices;'` ejecuta la consulta SQL `DELETE FROM devices;`:
    - `DELETE FROM devices;` elimina todas las filas de la tabla `devices`. Es una operación fila-por-fila y mantiene el contador de transacciones (WAL); puede ser lenta si la tabla es grande.
    - Alternativa: `TRUNCATE devices;` es más rápida y resetea almacenamiento, pero debe usarse con cuidado si hay claves foráneas (usar `TRUNCATE ... CASCADE` con precaución).
  - `-P pager=off` evita que `psql` use el paginador (`less`) y fuerza la salida directa a la terminal (útil en scripts).

- `psql -h localhost -U iot_user -d iot_db -c 'SELECT COUNT(*) FROM devices;' -P pager=off`  
  - Ejecuta `SELECT COUNT(*) FROM devices;` para comprobar que la tabla quedó vacía después del `DELETE`. Devuelve `0` si la eliminación fue total.

- `sudo systemctl restart acquire_data.service`  
  - Reinicia el servicio systemd `acquire_data.service` (el componente que repuebla/monitoriza dispositivos y adquiere datos). Al reiniciarlo, el servicio re-ejecuta su rutina de descubrimiento y/o read-initialization.

- `sleep 5`  
  - Espera 5 segundos para dar tiempo al servicio reiniciado a realizar un primer ciclo de escaneo/repopulación.

- `export PGPASSWORD='DAms15820'; psql -h localhost -U iot_user -d iot_db -c 'SELECT device_id, device_type, ip_address, port, status, updated_at FROM devices ORDER BY updated_at DESC LIMIT 20;' -P pager=off`  
  - Vuelve a exportar la contraseña (por seguridad en el contexto del comando encadenado) y ejecuta un `SELECT` para listar hasta 20 dispositivos ordenados por la fecha de actualización más reciente (`updated_at DESC`). Permite comprobar si el servicio repobló la tabla con dispositivos detectados tras el reinicio.

2) Los bloques repetidos con `sleep 10` y el mismo `SELECT`:
```
bash -lc "sleep 10; export PGPASSWORD='DAms15820'; psql -h localhost -U iot_user -d iot_db -c 'SELECT device_id, device_type, ip_address, port, status, updated_at FROM devices ORDER BY updated_at DESC LIMIT 20;' -P pager=off"
```
- Se repiten varias veces (sleep 10 + SELECT) para esperar más tiempo y verificar progresivamente si la tabla `devices` sigue repoblándose en ciclos sucesivos del servicio. Cada bloque espera 10 segundos y vuelve a comprobar los últimos dispositivos detectados. Esto es útil cuando el proceso de descubrimiento tarda más de un ciclo o hay retrasos en la red.

Resumen del flujo lógico y objetivo
- Backup (recomendado) → Borrado total de `devices` → Verificar que quedó vacía → Reiniciar el servicio de adquisición → Esperar brevemente → Comprobar si el servicio repuebla la tabla → Repetir comprobaciones con esperas para asegurar estabilidad.

Recomendaciones y consideraciones de seguridad
- Siempre hacer backup antes de `DELETE`/`TRUNCATE`.
- Si la tabla tiene relaciones (FK), `DELETE FROM devices;` puede fallar o dejar huérfanas otras tablas. Revisar dependencias:
  - Para ver restricciones:  
    - `psql -h localhost -U iot_user -d iot_db -c "\d devices"`
- Mejor usar transacciones para pruebas:
  - `BEGIN; DELETE FROM devices WHERE ...; ROLLBACK;` (prueba sin aplicar) o `COMMIT;` para aplicar.
- Si la tabla es grande y quieres eliminar solo dispositivos inconsistentes, usa condiciones en `WHERE` en lugar de borrar todo:
  - Ejemplo: `DELETE FROM devices WHERE status = 'unknown' OR updated_at < now() - interval '30 days';`
- Si usas TRUNCATE para velocidad y no tienes FK que lo impidan:
  - `TRUNCATE TABLE devices RESTART IDENTITY;` (resetea secuencias).
- Evita guardar `PGPASSWORD` en procesos visibles; usa `~/.pgpass` con permisos 0600:
  - `echo "localhost:5432:iot_db:iot_user:DAms15820" >> ~/.pgpass && chmod 600 ~/.pgpass`

Comandos útiles de verificación adicionales
- Mostrar últimas 50 filas en sensor_data:
  - `psql -h localhost -U iot_user -d iot_db -c "SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 50;" -P pager=off`
- Revisar eventos del servicio systemd (logs):
  - `sudo journalctl -u acquire_data.service -n 200 --no-pager`
- Verificar que el servicio está activo:
  - `systemctl status acquire_data.service`

Conclusión
- El script que documentaste es una secuencia válida para limpiar la tabla de dispositivos y forzar que el servicio la repueble.  
- Documenté cada comando y su función principal, además de ofrecer alternativas seguras (backup, TRUNCATE vs DELETE, uso de WHERE) y recomendaciones para evitar eliminación accidental o pérdida de integridad.
``` ````// filepath: /home/daniel/repos/iot_streamlit/docs/resolucion_de_problemas_bd.md
### borrar y limpiar registros de la bd al presentar conflictos en dispositivos, cortes de energia o relaciones corruptas

Nota: los comandos descritos abajo son destructivos (eliminan filas). Antes de ejecutar cualquier borrado, realiza un backup completo de la base de datos:

- Hacer backup (dump):
  - exporta la contraseña y realiza un volcado comprimido:
    - export PGPASSWORD='DAms15820'  
    - pg_dump -h localhost -U iot_user -F c -b -v -f ~/iot_db_backup.dump iot_db

Explicación detallada línea por línea del bloque original

1) Comando concatenado original (ejecuta varias acciones en secuencia)
```
bash -lc "export PGPASSWORD='DAms15820'; psql -h localhost -U iot_user -d iot_db -c 'DELETE FROM devices;' -P pager=off; psql -h localhost -U iot_user -d iot_db -c 'SELECT COUNT(*) FROM devices;' -P pager=off; sudo systemctl restart acquire_data.service; sleep 5; export PGPASSWORD='DAms15820'; psql -h localhost -U iot_user -d iot_db -c 'SELECT device_id, device_type, ip_address, port, status, updated_at FROM devices ORDER BY updated_at DESC LIMIT 20;' -P pager=off"
```

- `bash -lc "..."`  
  - Ejecuta la cadena entre comillas con un shell (bash). Útil para encadenar varios comandos en una sola línea o dentro de scripts.

- `export PGPASSWORD='DAms15820'`  
  - Define la variable de entorno `PGPASSWORD` para que `psql` y otros clientes PostgreSQL puedan autenticarse sin prompt interactivo. (Es conveniente usar `.pgpass` para mayor seguridad.)

- `psql -h localhost -U iot_user -d iot_db -c 'DELETE FROM devices;' -P pager=off`  
  - `psql` es el cliente PostgreSQL.
  - `-h localhost` conecta al host local.
  - `-U iot_user` usa el usuario `iot_user`.
  - `-d iot_db` selecciona la base `iot_db`.
  - `-c 'DELETE FROM devices;'` ejecuta la consulta SQL `DELETE FROM devices;`:
    - `DELETE FROM devices;` elimina todas las filas de la tabla `devices`. Es una operación fila-por-fila y mantiene el contador de transacciones (WAL); puede ser lenta si la tabla es grande.
    - Alternativa: `TRUNCATE devices;` es más rápida y resetea almacenamiento, pero debe usarse con cuidado si hay claves foráneas (usar `TRUNCATE ... CASCADE` con precaución).
  - `-P pager=off` evita que `psql` use el paginador (`less`) y fuerza la salida directa a la terminal (útil en scripts).

- `psql -h localhost -U iot_user -d iot_db -c 'SELECT COUNT(*) FROM devices;' -P pager=off`  
  - Ejecuta `SELECT COUNT(*) FROM devices;` para comprobar que la tabla quedó vacía después del `DELETE`. Devuelve `0` si la eliminación fue total.

- `sudo systemctl restart acquire_data.service`  
  - Reinicia el servicio systemd `acquire_data.service` (el componente que repuebla/monitoriza dispositivos y adquiere datos). Al reiniciarlo, el servicio re-ejecuta su rutina de descubrimiento y/o read-initialization.

- `sleep 5`  
  - Espera 5 segundos para dar tiempo al servicio reiniciado a realizar un primer ciclo de escaneo/repopulación.

- `export PGPASSWORD='DAms15820'; psql -h localhost -U iot_user -d iot_db -c 'SELECT device_id, device_type, ip_address, port, status, updated_at FROM devices ORDER BY updated_at DESC LIMIT 20;' -P pager=off`  
  - Vuelve a exportar la contraseña (por seguridad en el contexto del comando encadenado) y ejecuta un `SELECT` para listar hasta 20 dispositivos ordenados por la fecha de actualización más reciente (`updated_at DESC`). Permite comprobar si el servicio repobló la tabla con dispositivos detectados tras el reinicio.

2) Los bloques repetidos con `sleep 10` y el mismo `SELECT`:
```
bash -lc "sleep 10; export PGPASSWORD='DAms15820'; psql -h localhost -U iot_user -d iot_db -c 'SELECT device_id, device_type, ip_address, port, status, updated_at FROM devices ORDER BY updated_at DESC LIMIT 20;' -P pager=off"
```
- Se repiten varias veces (sleep 10 + SELECT) para esperar más tiempo y verificar progresivamente si la tabla `devices` sigue repoblándose en ciclos sucesivos del servicio. Cada bloque espera 10 segundos y vuelve a comprobar los últimos dispositivos detectados. Esto es útil cuando el proceso de descubrimiento tarda más de un ciclo o hay retrasos en la red.

Resumen del flujo lógico y objetivo
- Backup (recomendado) → Borrado total de `devices` → Verificar que quedó vacía → Reiniciar el servicio de adquisición → Esperar brevemente → Comprobar si el servicio repuebla la tabla → Repetir comprobaciones con esperas para asegurar estabilidad.

Recomendaciones y consideraciones de seguridad
- Siempre hacer backup antes de `DELETE`/`TRUNCATE`.
- Si la tabla tiene relaciones (FK), `DELETE FROM devices;` puede fallar o dejar huérfanas otras tablas. Revisar dependencias:
  - Para ver restricciones:  
    - `psql -h localhost -U iot_user -d iot_db -c "\d devices"`
- Mejor usar transacciones para pruebas:
  - `BEGIN; DELETE FROM devices WHERE ...; ROLLBACK;` (prueba sin aplicar) o `COMMIT;` para aplicar.
- Si la tabla es grande y quieres eliminar solo dispositivos inconsistentes, usa condiciones en `WHERE` en lugar de borrar todo:
  - Ejemplo: `DELETE FROM devices WHERE status = 'unknown' OR updated_at < now() - interval '30 days';`
- Si usas TRUNCATE para velocidad y no tienes FK que lo impidan:
  - `TRUNCATE TABLE devices RESTART IDENTITY;` (resetea secuencias).
- Evita guardar `PGPASSWORD` en procesos visibles; usa `~/.pgpass` con permisos 0600:
  - `echo "localhost:5432:iot_db:iot_user:DAms15820" >> ~/.pgpass && chmod 600 ~/.pgpass`

Comandos útiles de verificación adicionales
- Mostrar últimas 50 filas en sensor_data:
  - `psql -h localhost -U iot_user -d iot_db -c "SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 50;" -P pager=off`
- Revisar eventos del servicio systemd (logs):
  - `sudo journalctl -u acquire_data.service -n 200 --no-pager`
- Verificar que el servicio está activo:
  - `systemctl status acquire_data.service`
>
### Secuebncia ordenada a ejecutar en el terminal linux de la jetson nano
```bash
bash -lc "export PGPASSWORD='DAms15820'; psql -h localhost -U iot_user -d iot_db -c 'DELETE FROM devices;' -P pager=off; psql -h localhost -U iot_user -d iot_db -c 'SELECT COUNT(*) FROM devices;' -P pager=off; sudo systemctl restart acquire_data.service; sleep 5; export PGPASSWORD='DAms15820'; psql -h localhost -U iot_user -d iot_db -c 'SELECT device_id, device_type, ip_address, port, status, updated_at FROM devices ORDER BY updated_at DESC LIMIT 20;' -P pager=off"
```
>
```bash
bash -lc "sleep 10; export PGPASSWORD='DAms15820'; psql -h localhost -U iot_user -d iot_db -c 'SELECT device_id, device_type, ip_address, port, status, updated_at FROM devices ORDER BY updated_at DESC LIMIT 20;' -P pager=off"
```
>
```bash
bash -lc "sleep 10; export PGPASSWORD='DAms15820'; psql -h localhost -U iot_user -d iot_db -c 'SELECT device_id, device_type, ip_address, port, status, updated_at FROM devices ORDER BY updated_at DESC LIMIT 20;' -P pager=off"
```
>
```bash
bash -lc "sleep 10; export PGPASSWORD='DAms15820'; psql -h localhost -U iot_user -d iot_db -c 'SELECT device_id, device_type, ip_address, port, status, updated_at FROM devices ORDER BY updated_at DESC LIMIT 20;' -P pager=off"
```