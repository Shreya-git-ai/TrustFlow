export const PAYPAL_CURRENCY_CODES = [
  'AUD', 'BRL', 'CAD', 'CNY', 'CZK', 'DKK', 'EUR', 'HKD', 'HUF', 'ILS', 'INR', 'JPY', 'MYR',
  'MXN', 'TWD', 'NZD', 'NOK', 'PHP', 'PLN', 'GBP', 'SGD', 'SEK', 'CHF', 'THB', 'USD',
] as const

export type CurrencyCode = typeof PAYPAL_CURRENCY_CODES[number]

const currencyNames = new Intl.DisplayNames(undefined, { type: 'currency' })

export function currencyName(code: string) {
  try { return currencyNames.of(code) || code } catch { return code }
}

export function currencySymbol(code: string) {
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency: code })
      .formatToParts(0)
      .find((part) => part.type === 'currency')?.value || code
  } catch { return code }
}

export function currencyFractionDigits(code: string) {
  try { return new Intl.NumberFormat(undefined, { style: 'currency', currency: code }).resolvedOptions().maximumFractionDigits }
  catch { return 2 }
}

export function formatMoney(amount: string | number, code: string) {
  const numeric = Number(amount)
  if (!Number.isFinite(numeric)) return `${code} ${amount}`
  try { return new Intl.NumberFormat(undefined, { style: 'currency', currency: code }).format(numeric) }
  catch { return `${code} ${numeric.toFixed(2)}` }
}
