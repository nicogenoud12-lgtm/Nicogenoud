# Investment Dashboard — Guía de Deploy

## Qué es esta app

Dashboard personal de inversiones conectado a la API de InvertirOnline (IOL).
Corre en tu CasaOS vía Docker Compose y expone el puerto 8080 (apuntable a Cloudflare Tunnel).

---

## Stack

| Capa | Tecnología |
|---|---|
| Backend | FastAPI + SQLAlchemy 2 + SQLite (WAL) + Alembic |
| Seguridad | JWT HS256 (python-jose) + bcrypt + Fernet (credenciales IOL) |
| Scheduler | APScheduler (snapshot + sync operaciones + dolar diario) |
| Frontend | Vite + React + Tailwind CSS (dark mode) + Recharts + React Query |
| Deploy | Docker Compose, bind mount `./data/` para SQLite |

---

## Estructura del proyecto

```
Nicogenoud/
├── docker-compose.yml
├── .env.example
├── data/                  ← SQLite vive acá (rsync-friendly, NO en volumen Docker)
├── backend/
│   ├── Dockerfile
│   ├── entrypoint.sh      alembic upgrade head → seed → uvicorn
│   ├── requirements.txt
│   ├── .env               ← crear desde .env.example (NO se commitea)
│   ├── alembic/           migraciones (corren automáticamente al iniciar)
│   └── app/
│       ├── main.py        FastAPI factory + CORS + lifespan scheduler
│       ├── config.py      Settings (pydantic-settings, lee backend/.env)
│       ├── models.py      User, IolCredential, OauthToken, Holding,
│       │                  PortfolioSnapshot, Operation, DolarQuote, AppSetting
│       ├── security.py    JWT + bcrypt directo (sin passlib)
│       ├── crypto.py      Fernet encrypt/decrypt (credenciales IOL)
│       ├── scheduler.py   APScheduler bootstrap desde AppSettings
│       ├── seed.py        idempotente: admin + settings defaults
│       ├── jobs/
│       │   ├── snapshot_job.py      holdings → dolar → snapshot diario
│       │   ├── operations_sync.py   /operaciones 2026-01-01..hoy (idempotente)
│       │   └── dolar_job.py         dolarapi.com → DolarQuote
│       ├── services/
│       │   ├── iol_auth.py          OAuth2 password/refresh + asyncio.Lock
│       │   ├── iol_client.py        httpx + tenacity (retry 401/429/5xx)
│       │   ├── classifier.py        clasificación activos + eventos operación
│       │   ├── ons_whitelist.py     whitelist ONs (MRCAD, MR35D, YMCJD…)
│       │   ├── portfolio_service.py refresh holdings + compute KPIs
│       │   ├── operations_service.py sync /operaciones → upsert
│       │   ├── dolar_service.py     dolarapi.com MEP/CCL/Blue/Oficial
│       │   └── pnl.py               P&L segregado por currency_kind
│       ├── routers/
│       │   ├── auth.py       POST /auth/login, GET /auth/me
│       │   ├── iol.py        connect/status/disconnect/refresh
│       │   ├── portfolio.py  holdings, kpis
│       │   ├── operations.py listado, sync, summary
│       │   ├── dolar.py      current, history
│       │   ├── settings.py   GET/PUT dolar_source, cron, scheduler
│       │   └── snapshots.py  listado, run-now, delete
│       └── tests/
│           └── test_classifier.py   13 tests (ONs, currency_kind, etc.)
└── frontend/
    ├── Dockerfile             node:20-alpine build → nginx:1.27-alpine
    ├── nginx.conf             SPA fallback + proxy /api → backend:8000
    └── src/
        ├── screens/
        │   ├── ResumenScreen       KPIs + evolución 90d + donut + top 5
        │   ├── TenenciasScreen     tabla por activo, filtro clase, refresh
        │   ├── OperacionesScreen   filtro event_kind + sync + summary cards
        │   ├── AnalisisScreen      donut + P&L bar + histórico + top/worst
        │   └── AjustesScreen       IOL connect/disconnect + dolar + scheduler
        ├── components/charts/
        │   ├── PortfolioLineChart  evolución ARS o USD (currency toggle)
        │   ├── AssetDonutChart     distribución por clase (CEDEAR/ON/Bono…)
        │   └── OperationsBarChart  P&L por símbolo (verde/rojo por cell)
        └── store/uiStore.js        Zustand: currency ARS|USD, sidebarOpen
```

---

## Clasificador de activos y operaciones

El `classifier.py` resuelve la heterogeneidad de la API de IOL:

### Clases de activos
`CEDEAR | Acción | Bono | ON | FCI | Letra | Otro`

Cascada de detección:
1. Campo `tipo` de IOL (TitulosPublicos → Bono, CEDEAR → CEDEAR, etc.)
2. Whitelist de ONs en `ons_whitelist.py` (base ticker sin sufijo D/C/O)
3. Prefijos de bonos soberanos (AL30, GD35, TX26…)
4. Mercado USA → CEDEAR
5. Campo `descripcion`
6. Fallback → "Otro" + WARNING en log

### Eventos de operación
`COMPRA | VENTA | RENTA | AMORTIZACION | DIVIDENDO | SUSCRIPCION | RESCATE | OTRO`

IOL puede etiquetar la renta de una ON como "Pago de dividendos", "Cupón",
"Renta" o "Pago de renta y amortización". El classifier prioriza el campo
`tipo` estructurado sobre la descripción libre para no confundir eventos.

### Especie de cobro (currency_kind)
`ARS | USD_MEP | USD_CABLE`

Detectado por sufijo del símbolo (`D` = MEP, `C` = CCL, `O` = cable) y por el
campo `moneda`. Almacenado en `Operation.currency_kind` para que `pnl.py` nunca
sume pesos con dólar cable.

---

## Variables de entorno (`backend/.env`)

```env
# App
APP_ENV=production
TZ=America/Argentina/Buenos_Aires
SQLITE_PATH=/data/app.db
CORS_ORIGINS=http://10.0.0.69:8080,https://inversiones.genoud-nube.com.ar

# Auth
JWT_SECRET=           # openssl rand -hex 32
JWT_ALG=HS256
JWT_EXPIRES_MIN=60
ADMIN_USERNAME=nico
ADMIN_PASSWORD=       # elegí uno seguro

# Encriptación (credenciales + tokens IOL en DB)
FERNET_KEY=           # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# IOL
IOL_BASE_URL=https://api.invertironline.com
IOL_TOKEN_PATH=/token
IOL_HTTP_TIMEOUT=20

# Dólar
DOLARAPI_BASE=https://dolarapi.com/v1
DEFAULT_DOLAR_SOURCE=MEP

# Scheduler
SCHEDULER_ENABLED=true
SNAPSHOT_CRON=55 23 * * *
DOLAR_CRON_MORNING=0 8 * * *
DOLAR_CRON_EVENING=50 23 * * *
OPERATIONS_YEAR=2026
```

---

## Endpoints API (`/api/v1`)

| Método | Path | Descripción |
|---|---|---|
| POST | /auth/login | `{username, password}` → JWT (60 min) |
| GET | /auth/me | usuario + `iol_connected` flag |
| POST | /iol/connect | guarda credenciales encriptadas, hace password grant |
| GET | /iol/status | connected, expires_at, last_error |
| POST | /iol/disconnect | borra IolCredential + OauthToken |
| POST | /iol/refresh | fuerza refresh del access token |
| GET | /portfolio/holdings?refresh= | tenencias actuales (refresh=true llama IOL) |
| GET | /portfolio/kpis | KPIs: totales ARS/USD, P&L, distribución por clase |
| GET | /operations?year=2026&event_kind= | operaciones filtradas |
| POST | /operations/sync?year=2026 | pull IOL → upsert (idempotente) |
| GET | /operations/summary?year=2026 | totales compras/ventas/renta/dividendos |
| GET | /dolar/current?source=MEP | cotización del día |
| GET | /dolar/history?source=MEP&days=90 | historial |
| GET | /settings | todas las AppSettings |
| PUT | /settings | actualiza (dolar_source, cron, scheduler, tz) |
| GET | /snapshots?days=180 | historial de snapshots |
| POST | /snapshots/run-now | genera snapshot manual ahora |
| DELETE | /snapshots/{id} | borra snapshot |

---

## Scheduler (APScheduler)

| Job | Cron default | Qué hace |
|---|---|---|
| snapshot + sync | `55 23 * * *` | refresh holdings → dolar → snapshot + sync operaciones 2026 |
| dolar morning | `0 8 * * *` | upsert MEP/CCL/Blue/Oficial desde dolarapi.com |
| dolar evening | `50 23 * * *` | ídem al cierre |

Los crons son parametrizables desde Ajustes en la UI (→ `PUT /settings`).

---

## Backup

El SQLite vive en `./data/app.db` (bind mount, no volumen Docker).
Incluilo en tu rsync diario al Toshiba:

```bash
rsync -av /home/genoud/Nicogenoud/data/ /mnt/toshiba/backups/Nicogenoud/data/
```

---

## Cloudflare Tunnel

Apuntá el tunnel a `http://localhost:8080` y agregá el dominio público a
`CORS_ORIGINS` en `backend/.env`:

```
CORS_ORIGINS=http://10.0.0.69:8080,https://inversiones.genoud-nube.com.ar
```

Luego `docker compose up -d --build` para que tome el nuevo env.

---

## Primer uso

1. Login con `ADMIN_USERNAME` / `ADMIN_PASSWORD`.
2. Ir a **Ajustes** → **Conexión IOL** → ingresar usuario y contraseña de IOL → **Conectar**.
3. Ir a **Tenencias** → **↻ Actualizar** (pull en vivo de IOL).
4. Ir a **Operaciones 2026** → **↻ Sincronizar** (trae operaciones desde 2026-01-01).
5. Ajustes → **Ejecutar snapshot ahora** → aparece el primer punto en el gráfico de evolución.

A partir del día siguiente el scheduler se encarga automáticamente.

---

## Agregar ONs no reconocidas

Si aparece una ON clasificada como "Otro" (ver logs del backend con `WARNING classify_asset`),
agregá el base ticker (sin sufijo D/C/O) a la lista en:

```
backend/app/services/ons_whitelist.py  →  ON_BASE_TICKERS
```

Luego rebuild:

```bash
docker compose up -d --build backend
```

---

## Tests del classifier

```bash
cd backend
pytest app/tests/ -v
# 13 passed — cubre ONs MEP/cable, amortización, dividendo CEDEAR, currency_kind
```
