/** The hex mark from the favicon tile: stroke follows text color, gold halo only. */
export function Logo({ size = 22 }: { size?: number }) {
  // Cropped to the mark so a 22px box is filled; the favicon tile padding is left out.
  return (
    <svg width={size} height={size} viewBox="8 4 48 56" fill="none" aria-hidden="true" className="block shrink-0">
      <polygon points="32,13 50.84,23.88 50.84,45.63 32,56.5 13.16,45.63 13.16,23.88" stroke="currentColor" strokeWidth="6" strokeLinejoin="miter" />
      <ellipse cx="32" cy="13" rx="15.1" ry="5.5" stroke="#E8C15A" strokeWidth="5" />
    </svg>
  );
}
