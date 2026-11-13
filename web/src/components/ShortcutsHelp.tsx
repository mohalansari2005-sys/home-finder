import { ArrowLeft, ArrowRight, Keyboard } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'

const Key = ({ children, label }: { children: ReactNode; label?: string }) => (
  <kbd aria-label={label} className="inline-flex h-8 min-w-8 items-center justify-center rounded-lg border bg-muted px-2 font-sans text-sm font-medium">{children}</kbd>
)

const ROWS: { keys: ReactNode; label: string }[] = [
  { keys: <Key>B</Key>, label: 'حفظ العقار المحدد أو إلغاء حفظه' },
  { keys: <Key>X</Key>, label: 'استبعاد العقار المحدد' },
  { keys: <Key label="السهم الأيسر"><ArrowLeft className="size-4" strokeWidth={1.75} aria-hidden /></Key>, label: 'العقار التالي' },
  { keys: <Key label="السهم الأيمن"><ArrowRight className="size-4" strokeWidth={1.75} aria-hidden /></Key>, label: 'العقار السابق' },
  { keys: <Key>?</Key>, label: 'عرض هذه القائمة' },
]

/** Desktop only: a visible button that opens the list (the "?" key does too). */
export function ShortcutsHelp({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  return (
    <>
      <Button variant="ghost" size="sm" className="h-9 text-muted-foreground" onClick={() => onOpenChange(true)}>
        <Keyboard aria-hidden />اختصارات لوحة المفاتيح
      </Button>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="gap-5 rounded-3xl p-6 shadow-xl sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="font-display text-lg font-bold">اختصارات لوحة المفاتيح</DialogTitle>
            <DialogDescription>لا تعمل أثناء الكتابة في أي حقل.</DialogDescription>
          </DialogHeader>
          <dl className="space-y-3">
            {ROWS.map((r) => (
              <div key={r.label} className="flex items-center justify-between gap-4">
                <dt>{r.keys}</dt>
                <dd className="text-sm">{r.label}</dd>
              </div>
            ))}
          </dl>
        </DialogContent>
      </Dialog>
    </>
  )
}
