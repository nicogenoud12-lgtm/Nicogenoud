// Rendimiento ponderado en el tiempo (TWR): encadena el rendimiento de cada tramo
// descontando la plata que entró o salió, así una compra no se lee como ganancia.
//   r_t = (V_t − V_{t−1} − F_t) / V_{t−1}
//   acumulado_t = Π (1 + r_i) − 1
// `points`: [{ value, flow }] en orden cronológico. `flow` = aportes (+) / retiros (−)
// desde el punto anterior. Devuelve, por punto, el rendimiento del tramo y el acumulado
// (ambos en %) y si hubo un movimiento de plata relevante para marcarlo en el gráfico.

// Movimientos menores a esto (sobre el valor anterior) no se marcan: evita ruido de centavos
export const FLOW_MARK_MIN_SHARE = 0.001;

export function timeWeightedReturns(points) {
  let growth = 1;
  return points.map((p, i) => {
    const value = Number(p.value) || 0;
    const flow = Number(p.flow) || 0;
    if (i === 0) {
      return { dayPct: null, cumPct: 0, flowMark: 0 };
    }
    const prev = Number(points[i - 1].value) || 0;
    // Sin valor previo (ej. primera compra de una clase) el tramo es sólo aporte: rendimiento 0
    const r = prev > 0 ? (value - prev - flow) / prev : 0;
    growth *= 1 + r;
    const base = prev > 0 ? prev : value;
    const flowMark = base > 0 && Math.abs(flow) >= base * FLOW_MARK_MIN_SHARE ? Math.sign(flow) : 0;
    return { dayPct: prev > 0 ? r * 100 : null, cumPct: (growth - 1) * 100, flowMark };
  });
}
