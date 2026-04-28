# Event Processing & Reporting System

## Overview

Este proyecto implementa un sistema de ingesta, procesamiento y consulta de eventos orientado a e-commerce, pensado para manejar volúmenes altos (millones de eventos por día) sin que eso impacte en la experiencia del cliente ni en los tiempos de respuesta de la API.

La idea principal es separar bien dos problemas que suelen estar mezclados:

1. Recibir eventos de forma confiable y sin frenar al cliente
2. Poder consultar métricas de negocio sin tener que escanear millones de filas cada vez

Para eso, el sistema está armado como un pipeline desacoplado, con procesamiento asíncrono y pre-agregación de datos.

---

## Arquitectura

El flujo general es el siguiente:

```
[ API ] → [ Redis Stream ] → [ Consumer ] → [ PostgreSQL ]
                                      ↓
                               [ Aggregator ]
                                      ↓
                               [ Query API ]
```

La clave acá es que cada componente hace una sola cosa, y la hace bien.

### Algunas decisiones importantes

* La ingesta está desacoplada de la base de datos
* El procesamiento es asíncrono
* Se asume que pueden haber duplicados (y se manejan)
* Se pre-calculan métricas para evitar queries pesadas
* Todo está pensado para poder escalar horizontalmente

---

## Componentes

### API (FastAPI)

La API tiene dos responsabilidades:

* recibir eventos
* exponer endpoints de consulta

#### Ingesta (`/events`, `/events/batch`)

* Valida input con Pydantic
* Convierte a modelos de dominio (dataclasses)
* Serializa a JSON
* Publica en Redis
* Responde rápido (204 No Content)

Una decisión clave acá es que **la API no escribe en la base de datos directamente**.
Esto permite absorber picos sin que la DB se convierta en cuello de botella.

---

### Redis Streams

Se usa Redis como queue intermedia.

¿Por qué Redis?

* Es simple de levantar y usar
* Tiene buen throughput
* Soporta consumer groups
* Se integra fácil con Python

---

### Consumer

El consumer:.

* Lee eventos desde Redis
* Procesa en batches
* Inserta en PostgreSQL

Además maneja varios casos importantes:

* **Duplicados** → constraint en DB (`event_id`)
* **Poison pills** → se detectan, se loguean y no bloquean la cola
* **Fallos parciales** → si falla el batch, se intenta evento por evento
* **Dead letter queue** → eventos que no se pueden procesar se guardan aparte

---

### PostgreSQL

Es la fuente de verdad del sistema.

Tablas principales:

* `events`: eventos crudos (inmutables)
* `sessions`: agrupación por sesión
* `users`: resolución básica de usuarios
* `daily_aggregates`: métricas pre-calculadas

Un detalle importante:
los eventos **no tienen `user_id`**, porque eso es un dato derivado.
Esto ayuda a mantener la ingesta desacoplada.

## Modelado de datos y resolución de usuarios

Dado que el enunciado no provee un identificador de usuario explícito (por ejemplo, un `user_id` autenticado), se implementó un modelo simple para poder agrupar actividad y reconstruir comportamiento.

El modelo se organiza en tres niveles:

* `events`: fuente de verdad (inmutable)
* `sessions`: agrupación de eventos
* `users`: entidad derivada

### Eventos

La tabla `events` almacena todos los eventos del sistema y se considera inmutable.

No incluye un `user_id` directamente. Esto permite:

* mantener la ingesta desacoplada de la lógica de identificación
* evitar agregar complejidad o latencia en el momento de recibir eventos
* poder modificar la estrategia de resolución de usuarios sin afectar datos históricos

En su lugar, cada evento incluye:

* `session_id`
* `user_ip`

que se utilizan como base para la resolución posterior.

---

### Sesiones

La tabla `sessions` permite agrupar eventos relacionados mediante `session_id`.

Esto facilita:

* reconstruir el flujo de navegación (journey)
* trabajar con una unidad lógica intermedia en lugar de eventos individuales
* asociar múltiples eventos a un mismo usuario una vez resuelta la identidad

---

### Usuarios

La tabla `users` representa una aproximación de identidad.

Dado que no hay autenticación, se utiliza una heurística simple:

* se agrupan eventos por (`store_id`, `user_ip`)
* se asigna un `user_id` interno (UUID)
* se mantiene ese mapping para reutilizarlo en futuras sesiones

Este enfoque permite estimar usuarios únicos sin depender de un identificador real.

---

### Resolución

La resolución de usuarios se realiza fuera del flujo de ingesta principal, en un proceso separado.

El proceso es:

1. Se procesan eventos nuevos
2. Se agrupan por `store_id` y `user_ip`
3. Se verifica si ya existe un `user_id` asociado
4. Si no existe, se crea uno nuevo
5. Se actualizan las sesiones correspondientes

Esto evita introducir lógica adicional en la API y mantiene el sistema desacoplado.

---

### Trade-offs

Este enfoque tiene limitaciones conocidas:

* `user_ip` no es un identificador confiable en todos los casos
* no permite identificar usuarios entre múltiples dispositivos
* puede agrupar usuarios distintos bajo una misma IP

Sin embargo, resulta adecuado para este contexto porque:

* es simple de implementar
* no impacta la performance de ingesta
* permite calcular métricas como usuarios únicos
* habilita reconstrucción de journeys

---

En resumen, se priorizó un modelo simple y desacoplado, suficiente para cubrir los requerimientos del ejercicio, y que permite evolucionar la lógica de identificación sin necesidad de reprocesar los eventos almacenados.


---

### Aggregator

Es un proceso batch que genera métricas por día.

* Corre periódicamente
* Procesa eventos recientes (ventana acotada)
* Hace upsert en `daily_aggregates`

Esto evita tener que hacer queries pesadas sobre la tabla de eventos.

---

### Query API

#### `/stores/{store_id}/report`

* Consulta directamente aggregates
* No toca eventos crudos
* Respuesta rápida y predecible

#### `/conversions/{checkout_id}/journey`

* Reconstruye el journey de un usuario
* Filtra eventos por sesión
* Limita hasta la conversión

---

## Flujo de datos

1. El cliente envía un evento
2. La API lo valida y lo manda a Redis
3. El consumer lo procesa y lo guarda
4. El aggregator genera métricas
5. Los endpoints de consulta leen datos optimizados

---

## Cómo correr el proyecto

### 1. Clonar repo

```bash
git clone https://github.com/Diego-Morardo/event-pipeline.git
cd event-pipeline
```

### 2. Levantar todo

```bash
docker compose up --build
```

Esto levanta:

* API
* Redis
* PostgreSQL
* Workers

### 3. Escalar workers (opcional)

```bash
docker compose up --scale worker=4
```

---

## Migraciones

El schema está definido con archivos SQL versionados:

```
db/migrations/
  001_create_events.sql
  002_create_sessions.sql
  003_create_users.sql
  004_create_daily_aggregates.sql
  005_indexes.sql
```

Esto permite mantener los cambios organizados y versionados, en lugar de tener un único script gigante.

---

## Performance

### Ingesta

* Desacoplada vía Redis
* Batch processing
* Escalable horizontalmente

### Reporting

* Basado en aggregates
* Queries rápidas
* No depende del volumen total de eventos

---

## Decisiones de diseño

### Separación de modelos

* Pydantic → validación
* Dataclass → dominio
* SQL → persistencia

Esto evita mezclar responsabilidades.

---

### Idempotencia

* `event_id` único
* `ON CONFLICT DO NOTHING`

Permite tolerar duplicados sin problemas.

---

### Batch processing

Reduce:

* overhead de red
* costo de inserts
* carga en la DB

---

## Notas sobre la estructura del proyecto

Para simplificar el ejercicio, la API está implementada completamente en `main.py`.

En un proyecto real, lo separaría en:

* `routes`
* `controllers`
* `services`
* `repositories`

También separaría claramente:

* **API de ingesta**
* **API de reporting**

Esto permitiría escalar y desplegar cada parte de forma independiente, especialmente en escenarios donde la carga de escritura y lectura es muy distinta.

---

## Mejoras futuras

Si tuviera más tiempo, hay varias mejoras que haría.

### Aggregation incremental

Hoy el aggregator recalcula una ventana completa.
Funciona, pero no es lo más eficiente.

Mejor alternativa:

* guardar el último timestamp procesado
* procesar solo nuevos eventos
* evitar recomputar datos viejos

---

### Separación de servicios

Dividir en servicios independientes:

* ingestion
* processing
* query

Esto permitiría escalar cada parte según necesidad y aislar fallos.

---

### Particionado en PostgreSQL

La tabla `events` va a crecer rápido.

Particionar por fecha ayudaría a:

* mejorar performance
* facilitar mantenimiento

---

### Mejor resolución de usuarios

Ahora se usa IP (simplificado).

Se podría mejorar usando:

* identificadores persistentes
* cookies / device id
* merge de usuarios entre sesiones

---

### Observabilidad

Agregar métricas y monitoreo:

* Prometheus
* Grafana
* tracing

Esto es clave en producción para detectar problemas.

---

## Conclusión

El sistema está pensado para:

* manejar alto volumen de eventos
* responder rápido
* ser resiliente ante fallos
* escalar de forma simple

Se priorizó una solución clara y mantenible, dejando espacio para evolucionar hacia algo más complejo si el contexto lo requiere.

---
