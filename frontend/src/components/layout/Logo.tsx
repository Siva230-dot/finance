import { Link } from "react-router-dom";

export function Monogram({ className = "h-9 w-9" }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} aria-hidden>
      <rect x="1" y="1" width="38" height="38" rx="8" fill="#25382D" stroke="#A58B58" strokeWidth="1" />
      <rect x="4.5" y="4.5" width="31" height="31" rx="5.5" fill="none" stroke="#A58B58" strokeOpacity=".45" strokeWidth=".75" />
      <text x="20" y="27.5" textAnchor="middle" fontFamily="Cormorant Garamond, Georgia, serif" fontStyle="italic" fontSize="21" fill="#E9E1D2">F</text>
    </svg>
  );
}

export function Logo({ onDark = false, to = "/" }: { onDark?: boolean; to?: string }) {
  return (
    <Link to={to} className="flex items-center gap-3" aria-label="AI FinanceMate home">
      <Monogram />
      <span className="leading-none">
        <span className={`block font-serif text-[22px] font-semibold ${onDark ? "text-[#F4F0E6]" : "text-ink"}`}>FinanceMate</span>
        <span className={`mt-1 block text-[9.5px] uppercase tracking-[0.3em] ${onDark ? "text-[#C2A56E]" : "text-gold"}`}>AI · Est. 2026</span>
      </span>
    </Link>
  );
}
