/**
 * components/Logo.tsx
 * Recoup brand logo inspired by Razorpay's identity system:
 * - Angular, sharp-cut "R" monogram with a return-arrow hook terminal.
 * - Wordmark: "recoup" in lowercase with a subtle upward curve on the final 'p' tail.
 * - Single dominant brand navy (#0C2651).
 */

interface LogoProps {
  className?: string;
  size?: number;
}

/**
 * Recoup Icon Monogram: Angular navy #0C2651 'R' with return-arrow hook.
 */
export function RecoupIconMark({ className = "", size = 26 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={{ flexShrink: 0 }}
      aria-hidden="true"
    >
      <g stroke="#0C2651" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
        {/* Sharp vertical stem */}
        <line x1="7" y1="5" x2="7" y2="27" />
        {/* Angular top loop */}
        <path d="M7 5H18C21.5 5 24 7.2 24 11C24 14.8 21.5 17 18 17H7" />
        {/* Angular leg curling into return-arrow hook */}
        <path d="M14.5 17L22 26.5L26 21.5" />
        <polyline points="23,21.5 26,21.5 26,24.5" />
      </g>
    </svg>
  );
}

/**
 * Recoup Full Lockup: Icon mark + "recoup" wordmark with curved 'p' tail.
 */
export function RecoupLogo({ className = "", size = 24 }: LogoProps) {
  return (
    <div
      className={`recoup-brand-lockup ${className}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "9px",
        userSelect: "none",
      }}
    >
      <RecoupIconMark size={size} />

      {/* SVG Wordmark */}
      <svg
        width="70"
        height="22"
        viewBox="0 0 70 22"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-label="recoup"
      >
        <text
          x="0"
          y="16"
          fontFamily="'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
          fontSize="18"
          fontWeight="600"
          fill="#0C2651"
          letterSpacing="-0.5px"
        >
          recoup
        </text>
      </svg>
    </div>
  );
}

export default RecoupLogo;
