import { useId } from "react";

/** Nav mark from brand/hexorcist-mark.svg. Hex stroke follows text color; gold halo stays fixed. */
export function Logo({ size = 22 }: { size?: number }) {
  const uid = useId().replace(/:/g, "");
  const hx = `${uid}-hx`;
  const hl = `${uid}-hl`;
  // viewBox "178 125 394 500" → width scales with the 394:500 aspect.
  const width = (size * 394) / 500;
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={width} height={size} viewBox="178 125 394 500" aria-hidden="true" className="block shrink-0">
      <defs>
        <clipPath id={hx}>
          <path d="M375 179.32L562.5 288.41V506.59L375 615.68L187.5 506.59V288.41Z" />
        </clipPath>
        <clipPath id={hl}>
          <ellipse cx="375" cy="179.32" rx="150" ry="45" />
        </clipPath>
      </defs>
      <path d="M375 179.32L562.5 288.41V506.59L375 615.68L187.5 506.59V288.41Z" fill="none" stroke="currentColor" strokeWidth="60" clipPath={`url(#${hx})`} />
      <ellipse cx="375" cy="179.32" rx="150" ry="45" fill="none" stroke="#E8C15A" strokeWidth="60" clipPath={`url(#${hl})`} />
    </svg>
  );
}
