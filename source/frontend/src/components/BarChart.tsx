/** Minimal accessible grouped bar chart (SVG), used for IELTS Task 1 and analytics. */
export function BarChart({ title, categories, series, unit = "", height = 260 }: { title?: string; categories: string[]; series: { name: string; values: number[] }[]; unit?: string; height?: number }) {
  const W = 640, H = height, pad = { l: 44, r: 12, t: title ? 30 : 12, b: 48 };
  const max = Math.max(1, ...series.flatMap((s) => s.values));
  const nice = Math.ceil(max / 10) * 10 || 10;
  const cw = (W - pad.l - pad.r) / categories.length;
  const bw = Math.min(36, (cw - 16) / series.length);
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - v / nice);
  const fills = ["#3a6fe0", "#c39a3a", "#10b981", "#a855f7"];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={title}>
      {title && <text x={W / 2} y={18} textAnchor="middle" className="fill-current text-[13px] font-semibold">{title}</text>}
      {[0, 0.25, 0.5, 0.75, 1].map((f) => (
        <g key={f}><line x1={pad.l} x2={W - pad.r} y1={y(nice * f)} y2={y(nice * f)} stroke="currentColor" strokeOpacity={0.12} />
          <text x={pad.l - 6} y={y(nice * f) + 4} textAnchor="end" className="fill-current text-[10px] opacity-60">{Math.round(nice * f)}{unit}</text></g>
      ))}
      {categories.map((c, i) => (
        <g key={c}>
          {series.map((s, k) => {
            const x = pad.l + i * cw + (cw - bw * series.length) / 2 + k * bw;
            return <g key={s.name}><rect x={x} y={y(s.values[i])} width={bw - 3} height={Math.max(0, y(0) - y(s.values[i]))} rx={3} fill={fills[k % 4]} />
              <text x={x + (bw - 3) / 2} y={y(s.values[i]) - 4} textAnchor="middle" className="fill-current text-[9px] opacity-70">{s.values[i]}</text></g>;
          })}
          <text x={pad.l + i * cw + cw / 2} y={H - pad.b + 16} textAnchor="middle" className="fill-current text-[11px]">{c}</text>
        </g>
      ))}
      {series.length > 1 && series.map((s, k) => (
        <g key={s.name} transform={`translate(${pad.l + k * 90}, ${H - 14})`}><rect width={10} height={10} rx={2} fill={fills[k % 4]} /><text x={14} y={9} className="fill-current text-[11px]">{s.name}</text></g>
      ))}
    </svg>
  );
}
