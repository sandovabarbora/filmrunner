/** Small round avatar shared by the viewer and the editor's Crew tab (FR-18). */
export function Avatar({ name, photoUrl, size = 32 }: { name: string; photoUrl: string | null | undefined; size?: number }) {
  const style = { width: size, height: size, fontSize: Math.round(size * 0.4) };
  if (photoUrl) {
    return <img className="avatar" src={photoUrl} alt="" style={style} width={size} height={size} />;
  }
  const initials = name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
  return (
    <span className="avatar avatar-fallback" style={style} aria-hidden="true">
      {initials || "?"}
    </span>
  );
}
