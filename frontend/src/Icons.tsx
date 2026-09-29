// Иконки навигации и статусов: inline SVG (без библиотек), декоративные — скрыты от скринридеров.
import type { ReactNode } from "react";

function Icon({ children, size = 22 }: { children: ReactNode; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

export const BookIcon = () => (
  <Icon>
    <path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z" />
    <path d="M19 19v2H6" />
  </Icon>
);
export const SunIcon = () => (
  <Icon>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </Icon>
);
export const SparkIcon = () => (
  <Icon>
    <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z" />
  </Icon>
);
export const FlagIcon = () => (
  <Icon>
    <path d="M5 21V4" />
    <path d="M5 4h12l-2 4 2 4H5" />
  </Icon>
);
export const TrophyIcon = () => (
  <Icon>
    <path d="M8 4h8v5a4 4 0 0 1-8 0z" />
    <path d="M8 6H4v1a4 4 0 0 0 4 4M16 6h4v1a4 4 0 0 1-4 4M12 13v4M8 21h8M10 17h4" />
  </Icon>
);
export const FlameIcon = () => (
  <Icon size={18}>
    <path d="M12 3c1 3 5 5 5 10a5 5 0 0 1-10 0c0-2 1-3 2-4 0 2 1 3 2 3 0-3-1-5 1-9z" />
  </Icon>
);
export const UserIcon = () => (
  <Icon>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21a8 8 0 0 1 16 0" />
  </Icon>
);
export const MoonIcon = () => (
  <Icon size={18}>
    <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />
  </Icon>
);
export const PencilIcon = () => (
  <Icon size={20}>
    <path d="M4 20l1-4L16.5 4.5a2 2 0 0 1 3 3L8 19z" />
  </Icon>
);
export const LogoutIcon = () => (
  <Icon size={18}>
    <path d="M10 4H5v16h5M15 8l4 4-4 4M19 12H9" />
  </Icon>
);
