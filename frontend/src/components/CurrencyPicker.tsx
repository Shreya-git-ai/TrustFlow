import { useEffect, useId, useRef, useState } from 'react'
import { PAYPAL_CURRENCY_CODES, currencyName, currencySymbol } from '../utils/currency'
import './CurrencyPicker.css'

type CurrencyPickerProps = {
  id: string
  name: string
  defaultValue?: string
  onChange?: (currency: string) => void
}

export default function CurrencyPicker({ id, name, defaultValue = 'USD', onChange }: CurrencyPickerProps) {
  const [value, setValue] = useState(defaultValue)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const rootRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const listId = useId()
  const currencies = PAYPAL_CURRENCY_CODES.map((code) => ({ code, name: currencyName(code), symbol: currencySymbol(code) }))
    .sort((a, b) => a.name.localeCompare(b.name))
  const filtered = currencies.filter(({ code, name: label, symbol }) => `${code} ${label} ${symbol}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))

  useEffect(() => setValue(defaultValue), [defaultValue])

  useEffect(() => {
    if (open) searchRef.current?.focus()
  }, [open])

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false)
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    const form = rootRef.current?.closest('form')
    function onReset() {
      setValue(defaultValue)
      setQuery('')
      setOpen(false)
      onChange?.(defaultValue)
    }
    form?.addEventListener('reset', onReset)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
      form?.removeEventListener('reset', onReset)
    }
  }, [defaultValue, onChange])

  function choose(code: string) {
    setValue(code)
    setOpen(false)
    setQuery('')
    onChange?.(code)
  }

  return <div className="currency-picker" ref={rootRef}>
    <input type="hidden" name={name} value={value}/>
    <button id={id} className="currency-picker-trigger" type="button" aria-haspopup="listbox" aria-expanded={open} aria-controls={listId} onClick={() => setOpen((current) => !current)}>
      <span className="currency-picker-symbol">{currencySymbol(value)}</span><span className="currency-picker-code">{value}</span><span className="currency-picker-chevron" aria-hidden="true">⌄</span>
    </button>
    {open && <div className="currency-picker-menu">
      <label className="currency-picker-search-label" htmlFor={`${listId}-search`}>Search currencies</label>
      <input ref={searchRef} id={`${listId}-search`} className="currency-picker-search" type="search" value={query} placeholder="Search by name or code" onChange={(event) => setQuery(event.target.value)} autoComplete="off"/>
      <div className="currency-picker-options" id={listId} role="listbox" aria-label="Currencies">
        {filtered.length ? filtered.map(({ code, name: label, symbol }) => <button className="currency-picker-option" key={code} type="button" role="option" aria-selected={value === code} onClick={() => choose(code)}>
          <span className="currency-picker-option-symbol">{symbol}</span><span className="currency-picker-option-name"><strong>{label}</strong><small>{code}</small></span>{value === code && <span className="currency-picker-check" aria-hidden="true">✓</span>}
        </button>) : <p className="currency-picker-empty">No currencies found.</p>}
      </div>
    </div>}
  </div>
}
