const p = { fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' } as const;

export const HomeIcon = () => (
  <svg viewBox="0 0 24 24" {...p} aria-hidden="true"><path d="M3 11l9-7 9 7" /><path d="M5 10v10h14V10" /></svg>
);
export const BookIcon = () => (
  <svg viewBox="0 0 24 24" {...p} aria-hidden="true"><path d="M4 4h12a3 3 0 013 3v13H7a3 3 0 01-3-3z" /><path d="M8 9h7M8 13h5" /></svg>
);
export const ChartIcon = () => (
  <svg viewBox="0 0 24 24" {...p} aria-hidden="true"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></svg>
);
export const CameraIcon = () => (
  <svg viewBox="0 0 24 24" {...p} aria-hidden="true"><path d="M4 7h3l2-3h6l2 3h3v13H4z" /><circle cx="12" cy="13" r="4" /></svg>
);
export const MicIcon = () => (
  <svg viewBox="0 0 24 24" {...p} aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 11a7 7 0 0014 0M12 18v4" /></svg>
);
export const KeyboardIcon = () => (
  <svg viewBox="0 0 24 24" {...p} aria-hidden="true"><rect x="2" y="6" width="20" height="12" rx="2" /><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10" /></svg>
);
export const ChatIcon = () => (
  <svg viewBox="0 0 24 24" {...p} aria-hidden="true"><path d="M21 12a8 8 0 01-11.6 7.1L4 20l1-4.6A8 8 0 1121 12z" /></svg>
);
