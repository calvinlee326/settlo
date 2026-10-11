import useSWR from 'swr';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const BASE_CURRENCY = 'USD';

export const CURRENCIES = [
  { code: 'USD', label: 'US Dollar' },
  { code: 'TWD', label: 'New Taiwan Dollar' },
  { code: 'JPY', label: 'Japanese Yen' },
  { code: 'CNY', label: 'Chinese Yuan (RMB)' },
  { code: 'KRW', label: 'Korean Won' },
  { code: 'THB', label: 'Thai Baht' },
  { code: 'EUR', label: 'Euro' },
];

const CODES = new Set(CURRENCIES.map((c) => c.code));
const formatters = new Map();

export function formatMoney(amount, currency) {
  if (!formatters.has(currency)) {
    formatters.set(
      currency,
      new Intl.NumberFormat('en-US', { style: 'currency', currency })
    );
  }
  return formatters.get(currency).format(amount);
}

export const useDisplayCurrencyStore = create(
  persist(
    (set) => ({
      currency: BASE_CURRENCY,
      setCurrency: (currency) => set({ currency }),
    }),
    { name: 'settlo-currency' }
  )
);

export function useRates() {
  const { data } = useSWR('/rates', { revalidateOnFocus: false });
  return data?.rates;
}

// Balances come from the API in USD. Shows them in the viewer's chosen
// currency at today's rate; stays in USD until rates load.
export function useMoney() {
  const stored = useDisplayCurrencyStore((s) => s.currency);
  const rates = useRates();
  const wanted = CODES.has(stored) ? stored : BASE_CURRENCY;
  const rate = rates?.[wanted];
  const currency = rate ? wanted : BASE_CURRENCY;
  const factor = rate || 1;
  return {
    currency,
    rates,
    format: (usd) => formatMoney(usd * factor, currency),
  };
}
