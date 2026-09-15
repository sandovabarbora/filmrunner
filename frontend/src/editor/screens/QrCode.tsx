import qrcode from "qrcode-generator";

/** Renders `value` as a scannable QR code, module-by-module as SVG rects (no dangerouslySetInnerHTML). */
export function QrCode({ value, size = 176 }: { value: string; size?: number }) {
  const qr = qrcode(0, "M");
  qr.addData(value);
  qr.make();
  const count = qr.getModuleCount();
  const cell = size / count;
  const dark: { x: number; y: number }[] = [];
  for (let row = 0; row < count; row++) {
    for (let col = 0; col < count; col++) {
      if (qr.isDark(row, col)) dark.push({ x: col, y: row });
    }
  }
  return (
    <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} role="img" aria-label="QR code for the crew link">
      <rect width={size} height={size} fill="#fff" />
      {dark.map((d) => (
        <rect key={`${d.x}-${d.y}`} x={d.x * cell} y={d.y * cell} width={cell} height={cell} fill="#000" />
      ))}
    </svg>
  );
}
