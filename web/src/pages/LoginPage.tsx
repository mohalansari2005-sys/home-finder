import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { House, Loader2 } from 'lucide-react'
import { api, ApiError } from '../api/client'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export function LoginPage() {
  const [pw, setPw] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const nav = useNavigate()
  const qc = useQueryClient()
  async function submit(e: FormEvent) {
    e.preventDefault()
    setErr(null)
    setPending(true)
    try {
      await api('/api/login', { method: 'POST', body: JSON.stringify({ password: pw }) })
      await qc.invalidateQueries({ queryKey: ['me'] })
      nav('/')
    } catch (e) {
      setErr(e instanceof ApiError && e.status === 429 ? 'محاولات كثيرة، حاول بعد دقيقة' : 'كلمة المرور غير صحيحة')
    } finally {
      setPending(false)
    }
  }
  return (
    <main className="flex min-h-dvh items-center justify-center p-4">
      <Card className="w-full max-w-sm gap-4 rounded-3xl py-8">
        <div className="flex flex-col items-center gap-3 px-6 text-center">
          <span className="flex size-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
            <House className="size-6" strokeWidth={1.75} aria-hidden />
          </span>
          <h1 className="font-display text-2xl font-semibold">بيتنا</h1>
        </div>
        <CardContent className="px-6">
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="pw">كلمة مرور العائلة</Label>
              <Input id="pw" type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoFocus
                     autoComplete="current-password" aria-invalid={err ? true : undefined}
                     aria-describedby={err ? 'pw-err' : undefined} />
              {err && <p id="pw-err" role="alert" className="text-sm text-destructive">{err}</p>}
            </div>
            <Button type="submit" size="lg" className="w-full" disabled={pending}>
              {pending && <Loader2 className="animate-spin" aria-hidden />}
              دخول
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}
