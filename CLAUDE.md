# Nicogenoud — Investment Dashboard (IOL)

Dashboard personal de inversiones del usuario `nico`. Conecta a **InvertirOnline (IOL)** vía API, traquea el portfolio 2026 (holdings, operaciones, P&L, dividendos), corre en Docker en su CasaOS. Mono-usuario, sin invitaciones.

## ⚡ Deploy (lo más importante)

El usuario corre la app en CasaOS. **Cada vez que pusheamos cambios**, el comando que tiene que ejecutar él para deployar es:

```bash
cd ~/Nicogenoud && git pull && docker compose up -d --build backend frontend
```

- Sólo se rebuildea cuando hay código nuevo (Docker cache hace que sea rápido).
- Si los cambios son **sólo de backend**: `docker compose up -d --build backend`.
- Si son **sólo de frontend**: `docker compose up -d --build frontend`.
- Si tocás `requirements.txt` o `package.json`: forzar `--no-cache` puede ser necesario, pero generalmente no.

Después del deploy, **si tocamos lógica de clasificación, conversión FX o sync de operaciones**, decile al usuario que toque **"↻ Sincronizar"** en la pestaña Operaciones. El upsert es idempotente por `iol_numero` — re-aplica la lógica nueva a las operaciones existentes.

URL: `http://localhost:8085` (en su LAN: `http://10.0.0.69:8085`). Cloudflare Tunnel opcional.

## 🌿 Branch convention

**Siempre trabajamos en**: `claude/investment-dashboard-iol-aW0Ju`

No crear branches nuevas. No hacer PRs salvo que el usuario lo pida explícitamente. Push directo a esa branch.

## Stack

- **Backend**: Python 3.12 + FastAPI + SQLAlchemy 2 + SQLite (WAL) + Alembic + APScheduler
- **Frontend**: Vite + React + Tailwind (`darkMode: 'class'`, dark por defecto) + Recharts + React Query + Zustand
- **Auth**: JWT HS256 (`python-jose`) + bcrypt directo (sin passlib). Sesiones de 7 días (`JWT_EXPIRES_MIN=10080`).
- **Secretos IOL**: encriptados en DB con `cryptography.Fernet`.
- **HTTP cliente**: `httpx.AsyncClient` + `tenacity` (retry 401/429/5xx).
- **Deploy**: Docker Compose, bind mount `./data/:/data` para que `app.db` quede en el filesystem (rsync-friendly al Toshiba).

## Layout

```
Nicogenoud/
├── docker-compose.yml         backend (expose 8000) + frontend (8085:80)
├── DEPLOY.md                  guía de deploy detallada
├── data/                      bind mount — SQLite vive acá
├── backend/
│   ├── Dockerfile
│   ├── entrypoint.sh          alembic upgrade head → seed → uvicorn
│   ├── .env                   (NO commiteado; usar .env.example como template)
│   ├── alembic/versions/      migraciones (auto al boot)
│   └── app/
│       ├── main.py            FastAPI factory + lifespan scheduler
│       ├── config.py          Settings(pydantic-settings)
│       ├── models.py          todas las tablas SQLAlchemy
│       ├── schemas.py         Pydantic
│       ├── security.py        JWT + bcrypt
│       ├── crypto.py          Fernet helpers
│       ├── scheduler.py       APScheduler bootstrap
│       ├── seed.py            admin + AppSettings idempotente
│       ├── jobs/
│       │   ├── snapshot_job.py        holdings → dolar → PortfolioSnapshot
│       │   ├── operations_sync.py     /operaciones 2026 → upsert
│       │   ├── dolar_job.py           dolarapi.com (today only)
│       │   ├── iol_keepalive.py       refresh proactivo cada 12h
│       │   └── crypto_snapshot_job.py crypto holdings (Binance)
│       ├── services/
│       │   ├── iol_auth.py            OAuth2 password/refresh + per-user asyncio.Lock
│       │   ├── iol_client.py          httpx + tenacity
│       │   ├── classifier.py          classify_asset() + classify_event()
│       │   ├── ons_whitelist.py       whitelist ONs + normalize_ticker()
│       │   ├── dolar_service.py       fetch + backfill_historical_mep (ArgentinaDatos)
│       │   ├── portfolio_service.py   refresh holdings + compute_kpis (con FX)
│       │   ├── operations_service.py  sync + enrich con /movimientos + backfill MEP
│       │   ├── pnl.py                 operations_summary (FX bidireccional)
│       │   ├── binance.py             crypto live prices (primary)
│       │   ├── coingecko.py           crypto fallback
│       │   └── crypto_service.py
│       ├── routers/                   auth, iol, portfolio, operations, dolar, settings, snapshots, crypto
│       └── tests/                     test_classifier.py + test_pnl.py
└── frontend/src/
    ├── screens/                       Resumen, Tenencias, Operaciones, Analisis, Crypto, Ajustes
    ├── components/charts/             PortfolioLineChart, AssetDonutChart, OperationsBarChart
    ├── store/uiStore.js               Zustand: currency (ARS|USD), sidebarOpen
    ├── api/                           axios clients
    └── utils/format.js                formatARS, formatUSD, formatDate, formatNumber
```

## 💰 Modelo de datos clave

- **User** — admin único seedado desde `ADMIN_USERNAME` / `ADMIN_PASSWORD`.
- **IolCredential** — `user_id` UQ, `iol_password_enc` (Fernet).
- **OauthToken** — `access_token_enc`, `refresh_token_enc`, `*_expires_at`, `last_keepalive_at`.
- **Holding** — UQ `(user_id, mercado, simbolo)`; `clase` clasificado, `valuacion_ars/usd`, `ganancia_dinero` (P&L no realizada por activo).
- **Operation** — UQ `(user_id, iol_numero)` idempotente. Columnas clave:
  - **`event_kind`** ∈ `{COMPRA, VENTA, RENTA, AMORTIZACION, DIVIDENDO, SUSCRIPCION, RESCATE, OTRO}`
  - **`currency_kind`** ∈ `{ARS, USD_MEP, USD_CABLE}`
  - `monto_neto` (calculado desde `montoOperado ± comisiones ± IVA ± derechos`, signo según event_kind).
  - `raw_json` para auditoría.
- **PortfolioSnapshot** — UQ `(user_id, date)`; `total_ars`, `total_usd`, `dolar_rate`, `breakdown_json`.
- **DolarQuote** — UQ `(date, source)`; sources `MEP|CCL|Blue|Oficial`. **Histórico MEP** backfilleado desde ArgentinaDatos.
- **AppSetting** — k/v; keys importantes: `dolar_source`, `scheduler_enabled`, `snapshot_cron`, `iol_keepalive_cron`, `tz`, `operations_year`.

## 🌐 Endpoints clave (prefix `/api/v1`)

| Router | Rutas |
| --- | --- |
| auth | `POST /auth/login`, `GET /auth/me` |
| iol | `POST /iol/connect`, `GET /iol/status`, `POST /iol/disconnect`, `POST /iol/refresh` |
| portfolio | `GET /portfolio/holdings?refresh=`, `GET /portfolio/kpis`, `GET /portfolio/accounts` |
| operations | `GET /operations?year=2026`, `POST /operations/sync`, `GET /operations/summary?year=2026` |
| dolar | `GET /dolar/current?source=`, `GET /dolar/history`, **`POST /dolar/backfill?desde=&hasta=`** |
| settings | `GET /settings`, `PUT /settings` |
| snapshots | `GET /snapshots`, `POST /snapshots/run-now`, `DELETE /snapshots/{id}` |

Todos requieren `Depends(get_current_user)` excepto `/auth/login`.

## 🧠 Lógica de negocio crítica

### Clasificación de activos (`services/classifier.py` + `ons_whitelist.py`)

`classify_asset(simbolo, tipo, descripcion, mercado)` devuelve **CEDEAR / Acción / Bono / ON / FCI / Letra / Otro** usando cascada:
1. `tipo` IOL (mapeo `_TIPO_MAP`)
2. **Whitelist de ONs** (`ON_BASE_TICKERS` — Mastellone, YPF YMCJ/YMCI/YM30–YM42, Pampa, IRSA, etc.)
3. Prefijos soberanos (AL30, GD30, TX26, etc.)
4. Heurísticas por descripción / mercado

**`normalize_ticker(simbolo)`** devuelve `(base, suffix)`:
- Sufijo `D` → USD_MEP
- Sufijo `C` → USD_CABLE
- Sufijo `O` → **depende del asset_class**: si es ON argentina → ARS (la O es parte del ticker, e.g. YM34O = YPF); si es CEDEAR → USD_CABLE.
- Marker ` US$` / ` USD` / ` U$S` al final (IOL usa esto en CEDEAR USD): tratado como sufijo D.

`classify_event(tipo, descripcion, simbolo, moneda, asset_class)` normaliza el `tipo` crudo de IOL a `event_kind` + detecta `currency_kind`. **IMPORTANTE**: IOL puede mandar "Pago de dividendos" para renta de ONs — el classifier lo recategoriza a RENTA si `asset_class == "ON"`.

### Conversión FX bidireccional (`services/pnl.py` + `portfolio_service.compute_kpis`)

**Las 4 KPIs (Compras, Ventas, Renta, Dividendos) NO se muestran segregadas por moneda.** Cada operación se convierte a **ambas** monedas usando el **MEP histórico del día de `fecha_operada`**, después se suman:
- USD ops: `usd = amount; ars = amount × MEP_del_día`
- ARS ops: `ars = amount; usd = amount ÷ MEP_del_día`

El frontend togglea entre `total_*_ars` y `total_*_usd` según `useUiStore`. Sin moneda nativa fija — el usuario elige.

**Fuente histórica**: `api.argentinadatos.com/v1/cotizaciones/dolares/bolsa` (serie completa MEP). `backfill_historical_mep()` lo trae idempotente en cada sync. Fallback: fecha más cercana anterior, luego posterior. Si no hay MEP para una fecha, esa op se cuenta sólo en su moneda nativa (no se infla artificialmente) — `fx_missing_count` lo reporta para que la UI muestre un warning ámbar.

**P&L no realizada** sale de `Holding.ganancia_dinero` (ARS, de IOL). El USD se calcula dividiendo por la cotización MEP **actual** (no histórica) — es una valoración en vivo.

**P&L realizada — NO existe**. El usuario no vende. Removida del backend y frontend (commit `e3fd6d6`).

### IOL keep-alive

Job `iol_keepalive.py` corre cada 12h. Si `refresh_expires_at` está a <7 días, fuerza refresh. Si refresh falla, intenta password grant con credenciales encriptadas guardadas. Margen de seguridad en `iol_auth.py`: 120s antes del vencimiento. Resultado: el usuario **no debe re-loguearse en IOL** salvo que cambie la password en el portal oficial.

### Operations sync flow

1. `IolClient.get_operaciones(estado="terminadas", desde=2026-01-01, hasta=hoy)`
2. Upsert por `iol_numero`. **Importante**: usar `cantidadOperada` antes de `cantidad` (este último es VN nominal para bonos, no cantidad ejecutada). Calcular `monto_neto` desde `montoOperado ± fees`, signo según event_kind.
3. `_enrich_with_movimientos`: cruza con IOL `/movimientos` para obtener el **neto** post-retención de dividendos/renta (IOL `/operaciones` da el **bruto**).
4. `backfill_historical_mep`: trae MEP histórico de ArgentinaDatos para todo el año.

## 🛠️ Tests

```bash
cd backend && python -m pytest app/tests/ -v
```

Cubre:
- `test_classifier.py` (18 tests): normalize_ticker, is_on, classify_asset, classify_event con casos reales (MRCAD, YM34O, AAPL US$, YM39D, etc.)
- `test_pnl.py` (5 tests): conversión bidireccional, missing FX, nearest-date fallback, AMORTIZACION en bucket renta, by_mes.

**Antes de pushear cambios al classifier o a pnl.py, correr los tests.**

## 📋 Convenciones / reglas

- **Idioma**: comentarios en código y mensajes UI en español rioplatense (el usuario habla español, sin embargo el código y nombres internos están en inglés cuando son convención del framework — e.g. `event_kind`, `currency_kind`).
- **Branch**: siempre `claude/investment-dashboard-iol-aW0Ju`. NO crear PRs salvo pedido explícito.
- **Commits**: en inglés, conventional-ish (`feat:`, `fix:`, `refactor:`). Incluir el footer `https://claude.ai/code/...` (lo agrega automáticamente el harness).
- **No agregar emojis** a código ni commits (sólo si el usuario lo pide).
- **No crear archivos .md de docs ni README extra** sin pedido explícito. Excepción: `CLAUDE.md` (este archivo) y `DEPLOY.md` (ya existe).
- **No skipear hooks** (`--no-verify`).
- **Migraciones Alembic**: si tocás `models.py`, generar migración. Auto-corren al boot por `entrypoint.sh`.

## 🐛 Bugs ya corregidos (no romper)

| Fix | Commit / archivo | Qué arregla |
| --- | --- | --- |
| Cantidad EDN 30000 → 16 | `operations_service.py:115` usa `cantidadOperada` primero | IOL `cantidad` es VN para bonos |
| Monto neto desde componentes | `operations_service.py:122-130` | Antes leía `monto` (bruto VN), ahora calcula desde fees |
| `AAPL US$` → ARS bug | `ons_whitelist.py:83-85` markers ` US$`/` USD`/` U$S` → suffix D | IOL marca CEDEAR USD así |
| `YM34O` clasificado USD_CABLE | `ons_whitelist.py` whitelist YM30-YM42 + `classifier.py:_currency_kind_from` toma `asset_class` para sufijo O | O es parte del ticker en ONs argentinas |
| Renta/dividendos brutos | `_enrich_with_movimientos` cruza con IOL `/movimientos` | Para obtener neto post-retención |
| KPIs partidas ARS/USD | `pnl.py` + `portfolio_service.py` con conversión MEP histórica | Antes dropeaba la mitad de las ops al togglear moneda |
| P&L realizada inútil | Removida totalmente | Usuario no vende |
| IOL session expira | `iol_keepalive.py` job 12h + password grant fallback | Antes vencía a los 30 días sin actividad |

## 🧪 Verificación end-to-end

Después de cambios significativos, decile al usuario:
1. `cd ~/Nicogenoud && git pull && docker compose up -d --build backend frontend`
2. Hard refresh del browser (Ctrl+Shift+R).
3. Operaciones → **↻ Sincronizar** (re-procesa con la lógica nueva).
4. Verificar la KPI o feature que tocamos.

## ⚙️ Variables de entorno clave (`backend/.env`)

- `JWT_SECRET` — `openssl rand -hex 32`
- `JWT_EXPIRES_MIN=10080` — 7 días
- `FERNET_KEY` — `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- `ADMIN_USERNAME=nico`, `ADMIN_PASSWORD=<set on first boot>`
- `SCHEDULER_ENABLED=true`
- `OPERATIONS_YEAR=2026`
- `BINANCE_API_KEY` / `BINANCE_API_SECRET` (opcional, read-only — para evitar geo-blocking en crypto)

## 🎯 TL;DR para futuros chats

1. Trabajar en branch `claude/investment-dashboard-iol-aW0Ju`.
2. Después de pushear, decirle al usuario que corra el comando de deploy + Sincronizar.
3. No mezclar ARS y USD sin conversión MEP histórica.
4. No agregar P&L realizada de vuelta.
5. Si tocás clasificación o agregación, correr `pytest` antes de pushear.
6. Idempotencia: todo lo que sincroniza con IOL es idempotente por `iol_numero` o `(date, source)`.
