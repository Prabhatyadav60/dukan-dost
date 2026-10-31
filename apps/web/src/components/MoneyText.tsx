import { formatPaise } from '../lib/money';

export function MoneyText({ paise, className }: { paise: number; className?: string }) {
  return <span className={className}>{formatPaise(paise)}</span>;
}
