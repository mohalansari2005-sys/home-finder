import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '../api/client'

export function LoginPage() {
  const [pw, setPw] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const nav = useNavigate()
  const qc = useQueryClient()
  async function submit(e: FormEvent) {
    e.preventDefault()
    setErr(null)
    try {
      await api('/api/login', { method: 'POST', body: JSON.stringify({ password: pw }) })
      await qc.invalidateQueries({ queryKey: ['me'] })
      nav('/')
    } catch (e) {
      setErr(e instanceof ApiError && e.status === 429 ? 'محاولات كثيرة، حاول بعد دقيقة' : 'كلمة المرور غير صحيحة')
    }
  }
  return (
    <div className="flex min-h-full items-center justify-center p-6">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-2xl bg-white p-6 shadow">
        <h1 className="text-2xl font-semibold text-brand">بيتنا</h1>
        <label className="block">
          <span className="text-sm text-slate-600">كلمة مرور العائلة</span>
          <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoFocus
                 className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" />
        </label>
        {err && <p role="alert" className="text-sm text-red-600">{err}</p>}
        <button className="w-full rounded-xl bg-brand py-2 font-semibold text-white">دخول</button>
      </form>
    </div>
  )
}
