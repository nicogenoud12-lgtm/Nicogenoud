# Nicogenoud — Investment Dashboard (IOL)

Dashboard personal de inversiones del usuario `nico`. Conecta a **InvertirOnline (IOL)** vía API, traquea el portfolio desde 2026 (holdings, operaciones, P&L, dividendos), corre en Docker en su CasaOS. Mono-usuario, sin invitaciones (para otra cuenta de IOL se levanta otra instancia, ver Deploy).

## ⚡ Deploy (lo más importante)

El usuario corre la app en CasaOS. **Cada vez que pusheamos cambios**, el comando que tiene que ejecutar él para deployar es:

```bash
cd ~/Nicogenoud && git pull && docker compose up -d --build backend frontend
```

- Sólo se rebuildea cuando hay código nuevo (Docker cache hace que sea rápido).
- Si los cambios son **sólo de backend**: `docker compose up -d --build backend`.
- Si son **sólo de frontend**: `docker compose up -d --build frontend`.
- Si tocás `requirements.txt` o `package.json`: forzar `--no-cache` puede ser necesario, pero generalmente no.

**Segunda instancia (cuenta IOL del papá)**: corre en `~/Nicogenoud-papa`, puerto `8086`, creada con `scripts/nueva-instancia.sh` (ver DEPLOY.md). Para actualizar la principal y todas las `Nicogenoud-*` de una:

```bash
cd ~/Nicogenoud && ./scripts/deploy.sh            # o ./scripts/deploy.sh backend
```

El puerto del frontend sale de `FRONTEND_PORT` (`.env` en la raíz, default 8085). No hardcodear puertos en `docker-compose.yml`.

Después del deploy, **si tocamos lógica de clasificación, conversión FX o sync de operaciones**, decile al usuario que toque **"↻ Sincronizar"** en la pestaña Operaciones. El upsert es idempotente por `iol_numero` — re-aplica la lógica nueva a las operaciones existentes.

URL: `http://localhost:8085` (en su LAN: `http://10.0.0.69:8085`). Cloudflare Tunnel opcional.

## 🌿 Branch convention

Los cambios se integran a **`main` vía PR** (el CasaOS del usuario hace `git pull` de `main`). Trabajar en la branch que asigne la sesión, abrir PR contra `main` y mergear sólo cuando el usuario lo pida.

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
│       │   ├── operations_sync.py     /operaciones año en curso → upsert
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
│       │   ├── history_service.py     reconstrucción de snapshots hacia atrás (precios históricos IOL)
│       │   ├── binance.py             crypto live prices (primary)
│       │   ├── coingecko.py           crypto fallback
│       │   └── crypto_service.py
│       ├── routers/                   auth, iol, portfolio, operations, dolar, settings, snapshots, crypto
│       └── tests/                     test_classifier, test_pnl, test_portfolio, test_flows, test_crypto_*
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
| operations | `GET /operations?year=`, `GET /operations/years`, `POST /operations/sync?year=`, `POST\|GET /operations/sync-history` (segundo plano), `GET /operations/summary?year=` (year default = año en curso) |
| dolar | `GET /dolar/current?source=`, `GET /dolar/history`, **`POST /dolar/backfill?desde=&hasta=`** |
| settings | `GET /settings`, `PUT /settings` |
| snapshots | `GET /snapshots`, `POST /snapshots/run-now`, **`POST\|GET /snapshots/reconstruct`** (tarea en segundo plano), `DELETE /snapshots/{id}` |

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

**P&L realizada de IOL — NO existe**. El usuario no vende. Removida del backend y frontend (commit `e3fd6d6`). Excepción: las ventas de **crypto** sí registran P&L realizada (pedido explícito, PR #24).

### Evolución reconstruida (`services/history_service.py`)

"Reconstruir toda la historia" (Resumen con gráfico vacío, o Ajustes) arma snapshots diarios hacia atrás: `POST /snapshots/reconstruct` (sin `dias` = toda la historia) lanza en segundo plano `history_service.rebuild_history`: corre `sync_history` (todos los años), arranca el día antes de la primera operación (o donde empieza el MEP de ArgentinaDatos, si es después), refresca tenencias y reconstruye. Con `dias=N` hace sólo los últimos N días. `GET /snapshots` adelgaza a un punto por semana cuando hay más de 800 (`MAX_POINTS`); el período MAX pide 36500 días. Parte de las tenencias actuales (refresca antes), deshace compras/ventas/suscripciones/rescates para obtener la cantidad de cada día y la valúa con `seriehistorica` de IOL (sin ajustar). Cada posición se calibra contra la valuación actual (`factor = valuación / (cantidad × último precio)`, así los bonos que cotizan cada 100 VN quedan bien). Operaciones con sufijo de moneda (`AL30D`) suman a la tenencia base (`AL30`). Posiciones ya vendidas se agrupan por base y su factor sale de sus operaciones. **FCI no tiene serie**: se valúa a la cuotaparte actual (rendimiento pasado 0) y sus movimientos se toman por monto. Licitaciones y aportes que IOL manda como tipo "Otro" con cantidad cuentan como ingreso de títulos ("YPF CL.43 ADICIONAL" se cruza con YM43O por emisor + clase de la descripción). Un título cuya serie arranca >30 días después del inicio no existía antes (ON recién emitida) y no se valúa antes de su primera cotización; uno que ya no está y cuya serie terminó venció: hasta ese día se valúa con lo cobrado en la amortización final. **Splits** (YPFD ÷10, cambios de ratio de CEDEAR): la serie sin ajustar salta de escala; en Acción/CEDEAR un salto de un día que coincide con 2/3/4/5/10/20/25/50/100 (±12%) se toma como split y los precios y cantidades anteriores se pasan a la escala de hoy. En `utils/performance.js`, una tenencia cuya cantidad se multiplica por un ratio de split con valor casi igual cuenta como split (sin flujo, rinde lo que cambió el valor). El tooltip del gráfico muestra los 3 activos que más cambiaron ese día, para diagnosticar saltos. Los snapshots quedan con `source="reconstruido"`, **nunca pisan uno real** y se pueden regenerar. El gráfico muestra "Reconstruido hasta el …".

### Tareas largas en segundo plano (`services/background.py`)

**Cloudflare Tunnel corta los requests a los ~100 s** (no configurable), y nginx a los 300 s. Todo lo que pueda tardar más (historial, reconstrucción) va por `background.start(user_id, kind, fn)`: el POST lanza la tarea y devuelve `{estado, paso, resultado, error}`; el GET del mismo path devuelve el estado. En el frontend, `hooks/useBackgroundJob.js` lanza, consulta cada 2 s mientras `estado == "corriendo"` e invalida las queries al terminar. Registro en memoria (uvicorn con un solo proceso); las tareas son idempotentes, así que si el backend se reinicia se vuelven a lanzar. Los endpoints que lanzan tienen que ser `async def` (`asyncio.create_task` necesita el event loop).

### IOL keep-alive

Job `iol_keepalive.py` corre cada 12h. Si `refresh_expires_at` está a <7 días, fuerza refresh. Si refresh falla, intenta password grant con credenciales encriptadas guardadas. Margen de seguridad en `iol_auth.py`: 120s antes del vencimiento. Resultado: el usuario **no debe re-loguearse en IOL** salvo que cambie la password en el portal oficial.

### Operations sync flow

1. `IolClient.get_operaciones(estado="terminadas", desde=1/1 del año en curso, hasta=hoy)`
2. Upsert por `iol_numero`. **Importante**: usar `cantidadOperada` antes de `cantidad` (este último es VN nominal para bonos, no cantidad ejecutada). Calcular `monto_neto` desde `montoOperado ± fees`, signo según event_kind.
3. `_enrich_with_movimientos`: cruza con IOL `/movimientos` para obtener el **neto** post-retención de dividendos/renta (IOL `/operaciones` da el **bruto**).
4. `backfill_historical_mep`: trae MEP histórico de ArgentinaDatos para todo el año.

**Historial completo** ("Traer historial" en Operaciones): `POST /operations/sync-history` lanza en segundo plano `operations_service.sync_history`, que recorre los años hacia atrás llamando `sync_operations` por año. Corta tras 5 años seguidos vacíos una vez encontrada alguna operación, o en 2000. Un año pasado se sincroniza sólo `1/1 → 31/12` y, si viene vacío, no pide movimientos. **IOL a veces responde 500** a un año entero o a años viejos: `_fetch_operaciones` reintenta por trimestres y, si algún trimestre falla, por meses; `sync_year_safe` saltea un año que no responde (cuenta como vacío) y lo informa en `fallidos` / `anios_sin_operaciones`, así un error no corta toda la tarea. El selector de año sale de `GET /operations/years`.

## 🛠️ Tests

```bash
cd backend && python -m pytest app/tests/ -v
```

Cubre:
- `test_classifier.py`: normalize_ticker, is_on, classify_asset, classify_event con casos reales (MRCAD, YM34O, AAPL US$, YM39D, AMD/MCD/KO/YPFD en ARS, etc.)
- `test_pnl.py`: conversión bidireccional, missing FX, nearest-date fallback, AMORTIZACION, by_mes.
- `test_portfolio.py`: refresh_holdings no borra tenencias si falla un mercado; P&L no realizada por moneda.
- `test_flows.py`: flujos netos por snapshot (variación diaria de rendimiento).
- `test_crypto_*.py`: snapshots crypto, backfill, precios Binance, flujos crypto.

**Antes de pushear cambios al classifier o a pnl.py, correr los tests.**

## 🎨 Sistema visual (frontend)

Estética profesional y minimalista. Antes de tocar UI, respetar:
- **Tokens** en `frontend/src/index.css` (`--c-*`, claro y oscuro): neutros cálidos, un solo acento azul, `success`/`danger` sólo para subas y bajas. Bordes hairline sólidos, sin sombras, sin gradientes decorativos.
- **Clases**: `.card` + `.card-pad`, `.page-title`, `.section-title`, `.label` (sentence case, nunca `uppercase`), `.btn-primary` (monocromo, uno por vista), `.btn-secondary`, `.btn-ghost`, `.input`, `.segmented`, `.notice` (avisos neutros), `.num` (tabular-nums en columnas).
- **Componentes**: `PageHeader`, `Card`, `KpiCard` (`hero` = un solo número destacado por vista), `Delta` (variación con signo explícito), `DataTable`.
- **Gráficos** (`components/charts/chartTheme.js`): paleta categórica validada para daltonismo; el color sigue a la entidad (`colorFor`), nunca al ranking; más de 7 porciones → "Otros". Líneas de 2px, grilla hairline sólida, barras finas con punta redondeada. Los charts renderizan su propio card.
- **Evolución** (`PortfolioLineChart`): vista "Valor" con marcas en días con compras (punto lleno) o ventas/amortizaciones (punto hueco), y vista "Rendimiento" = TWR acumulado del período (`utils/performance.js`). El TWR se calcula **por tenencias** (cantidad de ayer × precio de hoy, usando `breakdown_json` de cada snapshot) más renta/dividendos (`ingreso_*`) y amortizaciones por símbolo (`amort_por_simbolo`), así que **no depende de los montos de las operaciones**. Crypto (sin cantidades) usa el respaldo por flujos. Un día con variación imposible (> 35% o < −90%) se marca como inconsistente y no se acumula. La vista elegida se guarda en `uiStore.evoMode`.
- **Sin emojis** en la UI (íconos SVG inline con `stroke="currentColor"`).

## 📋 Convenciones / reglas

- **Idioma**: comentarios en código y mensajes UI en español rioplatense (el usuario habla español, sin embargo el código y nombres internos están en inglés cuando son convención del framework — e.g. `event_kind`, `currency_kind`).
- **Branch**: la que asigne la sesión; integrar a `main` por PR cuando el usuario lo pida.
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
| AMD/MCD/KO/JD/NIO/INTC/YPFD/BA.C leídos como USD | `classifier._INTRINSIC_SUFFIX_TICKERS` | La última letra es parte del ticker, no sufijo de moneda. Si aparece un ticker nuevo así, agregarlo al set |
| Tenencias borradas si IOL falla | `refresh_holdings` sólo borra en mercados que respondieron | Un error transitorio vaciaba un mercado y el snapshot registraba la caída |
| Fechas un día antes | `utils/format.js` parsea `YYYY-MM-DD` en hora local | `new Date("YYYY-MM-DD")` es UTC → día anterior en UTC-3 |
| Compras como ganancia en el gráfico | `SnapshotOut.flujo_*` + tooltip de `PortfolioLineChart` | Variación diaria = (valor − anterior − flujo) / anterior. Flujo = compras/suscripciones − ventas/rescates/amortizaciones (renta y dividendos son rendimiento) |
| Año 2026 fijo | KPIs, sync y endpoints usan el año en curso (`kpi_year`) | Campos KPI renombrados sin `_2026` |

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
- `BINANCE_API_KEY` / `BINANCE_API_SECRET` (opcional, read-only — para evitar geo-blocking en crypto)

## 🎯 TL;DR para futuros chats

1. Integrar a `main` vía PR (el deploy hace `git pull` de `main`).
2. Después de pushear, decirle al usuario que corra el comando de deploy + Sincronizar.
3. No mezclar ARS y USD sin conversión MEP histórica.
4. No agregar P&L realizada de vuelta.
5. Si tocás clasificación o agregación, correr `pytest` antes de pushear.
6. Idempotencia: todo lo que sincroniza con IOL es idempotente por `iol_numero` o `(date, source)`.
