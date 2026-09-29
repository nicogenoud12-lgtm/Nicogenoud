import { useMemo, useState } from "react";

export default function DataTable({ columns, rows, emptyText = "Sin datos", footer }) {
  const [sort, setSort] = useState({ key: null, dir: "asc" });

  const sorted = useMemo(() => {
    if (!sort.key) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col) return rows;
    const get = col.value || ((r) => r[sort.key]);
    const arr = [...rows];
    arr.sort((a, b) => {
      const va = get(a);
      const vb = get(b);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (typeof va === "number" && typeof vb === "number")
        return sort.dir === "asc" ? va - vb : vb - va;
      const sa = String(va).toLowerCase();
      const sb = String(vb).toLowerCase();
      return sort.dir === "asc" ? sa.localeCompare(sb) : sb.localeCompare(sa);
    });
    return arr;
  }, [rows, sort, columns]);

  function onHeaderClick(c) {
    if (!c.sortable) return;
    setSort((s) =>
      s.key === c.key
        ? { key: c.key, dir: s.dir === "asc" ? "desc" : "asc" }
        : { key: c.key, dir: "asc" },
    );
  }

  return (
    <div className="card overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-border">
            {columns.map((c) => (
              <th
                key={c.key}
                onClick={() => onHeaderClick(c)}
                aria-sort={sort.key === c.key ? (sort.dir === "asc" ? "ascending" : "descending") : undefined}
                className={`px-4 h-10 text-left text-xs font-medium text-textMuted whitespace-nowrap ${
                  c.sortable ? "cursor-pointer select-none hover:text-text" : ""
                } ${c.align === "right" ? "text-right" : ""}`}
              >
                {c.label}
                {sort.key === c.key && (
                  <span className="ml-1 text-text">{sort.dir === "asc" ? "↑" : "↓"}</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-10 text-center text-textMuted">
                {emptyText}
              </td>
            </tr>
          ) : (
            sorted.map((r, i) => (
              <tr
                key={r.id ?? i}
                className="border-b border-border last:border-b-0 hover:bg-surfaceAlt/60 transition-colors"
              >
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={`px-4 h-11 whitespace-nowrap ${
                      c.align === "right" ? "text-right num" : ""
                    } ${c.className || ""}`}
                  >
                    {c.render ? c.render(r) : r[c.key]}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
        {footer && (
          <tfoot>
            <tr className="border-t border-border font-medium">
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={`px-4 h-11 whitespace-nowrap ${
                    c.align === "right" ? "text-right num" : "text-textMuted"
                  }`}
                >
                  {footer[c.key] ?? ""}
                </td>
              ))}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}
