// Rendimiento ponderado en el tiempo (TWR) de la cartera, encadenando tramos entre snapshots.
//
// Método principal (IOL): por tenencias. El rendimiento de un tramo es cómo le fue a lo que
// ya se tenía al inicio: Σ cant_ant × precio_actual (+ cobros) / Σ valor_ant − 1, sobre las
// tenencias presentes en ambos snapshots. No depende de los montos de las operaciones, así
// que una compra mal registrada o informada un día tarde no puede distorsionarlo.
//
// Respaldo (crypto o snapshots sin cantidades): por flujos. r = (V − V_ant − flujo) / V_ant.
//
// Un tramo con un movimiento imposible para una cartera (datos inconsistentes) no se acumula:
// se marca como no confiable y cuenta como 0.

// Movimientos de plata menores a esto (sobre el valor anterior) no se marcan en el gráfico
export const FLOW_MARK_MIN_SHARE = 0.001;
// Variación diaria máxima creíble; por encima es un error de datos, no mercado
export const MAX_DAILY_MOVE = 0.35;
// Un cobro mayor a esto (sobre el valor anterior) es un dato inconsistente y se ignora
const MAX_INCOME_SHARE = 0.2;

// Desdoblamiento (split) o cambio de ratio: la cantidad se multiplica por k y el valor casi
// no cambia. No es una compra ni una caída de precio: el tramo rinde lo que cambió el valor.
const SPLIT_RATIOS = [2, 3, 4, 5, 10, 20, 25, 50, 100];
function isSplit(p, c) {
  const valueRatio = c.value / p.value;
  if (!(valueRatio > 0.75 && valueRatio < 1.33)) return false;
  const q = c.qty / p.qty;
  return SPLIT_RATIOS.some((k) => Math.abs(q / k - 1) < 0.02 || Math.abs(q * k - 1) < 0.02);
}

function toMap(holdings) {
  const m = new Map();
  for (const h of holdings || []) {
    const qty = Number(h.qty);
    const value = Number(h.value);
    if (qty > 0 && value >= 0 && isFinite(qty) && isFinite(value)) m.set(h.key, { qty, value, sym: h.sym });
  }
  return m;
}

// Rendimiento y flujo implícito de un tramo a partir de las tenencias; null si no alcanza la data.
// `cur.amort` = { simbolo: monto } amortizado en el tramo: para ese bono el rendimiento es
// (valor actual + amortizado) / valor anterior, sin importar si IOL bajó el precio, la
// cantidad, o si venció y ya no está en la cartera.
function holdingsStep(prev, cur) {
  const a = toMap(prev.holdings);
  const b = toMap(cur.holdings);
  if (a.size === 0 || b.size === 0) return null;
  const amort = cur.amort || {};

  let base = 0;
  let end = 0;
  let flow = 0;
  const amortized = new Set();
  const split = new Set();
  for (const [key, p] of a) {
    if (p.value <= 0) continue;
    const c = b.get(key);
    const paid = Number(amort[p.sym]) || 0;
    if (paid > 0 && paid <= p.value * 1.5) {
      base += p.value;
      end += (c ? c.value : 0) + paid;
      amortized.add(key);
    } else if (c) {
      base += p.value;
      if (isSplit(p, c)) {
        end += c.value;
        split.add(key);
      } else {
        end += p.qty * (c.value / c.qty);
      }
    }
  }
  if (base <= 0) return null;

  // Flujo = plata puesta o sacada de las posiciones: cambio de cantidad × precio actual
  for (const [key, c] of b) {
    if (!amortized.has(key) && !split.has(key)) flow += (c.qty - (a.get(key)?.qty || 0)) * (c.value / c.qty);
  }
  for (const [key, p] of a) if (!b.has(key) && !amortized.has(key)) flow -= p.value;
  // Lo amortizado sale de las tenencias (se marca como retiro) aunque no afecte el rendimiento
  for (const key of amortized) flow -= Number(amort[a.get(key).sym]) || 0;

  let income = Number(cur.income) || 0;
  if (income < 0 || income > base * MAX_INCOME_SHARE) income = 0;

  return { r: (end + income) / base - 1, flow };
}

export function portfolioReturns(points) {
  let growth = 1;
  return points.map((p, i) => {
    const value = Number(p.value) || 0;
    if (i === 0) return { dayPct: null, cumPct: 0, flow: 0, flowMark: 0, unreliable: false };

    const prevPoint = points[i - 1];
    const prevValue = Number(prevPoint.value) || 0;
    let r = null;
    let flow = Number(p.flow) || 0;

    const step = holdingsStep(prevPoint, p);
    if (step) {
      r = step.r;
      flow = step.flow;
    } else if (prevValue > 0) {
      r = (value - prevValue - flow) / prevValue;
    }

    let unreliable = false;
    if (r != null && (!isFinite(r) || r <= -0.9 || Math.abs(r) > MAX_DAILY_MOVE)) {
      r = 0;
      unreliable = true;
    }
    if (r != null) growth *= 1 + r;

    const shareBase = prevValue > 0 ? prevValue : value;
    const flowMark = shareBase > 0 && Math.abs(flow) >= shareBase * FLOW_MARK_MIN_SHARE ? Math.sign(flow) : 0;
    return {
      dayPct: r == null ? null : r * 100,
      cumPct: (growth - 1) * 100,
      flow,
      flowMark,
      unreliable,
    };
  });
}
