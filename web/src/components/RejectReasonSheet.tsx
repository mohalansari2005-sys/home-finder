import { useId, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Drawer, DrawerContent, DrawerDescription, DrawerHeader, DrawerTitle } from '@/components/ui/drawer'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { useBreakpoint } from '../lib/breakpoint'
import { REASON_AR, REJECT_REASONS } from '../lib/factors'

export interface RejectChoice { reason_code?: string; note?: string }
interface Props { open: boolean; listingTitle?: string | null; onSubmit: (c: RejectChoice) => void; onCancel: () => void }

function Body({ onSubmit }: Pick<Props, 'onSubmit'>) {
  const [reason, setReason] = useState<string>()
  const [note, setNote] = useState('')
  const noteId = useId()
  const submit = () => {
    const n = note.trim()
    onSubmit({ ...(reason ? { reason_code: reason } : {}), ...(n ? { note: n } : {}) })
  }
  return (
    <div className="space-y-4 p-4 pt-2 md:p-0">
      {/* "multiple" renders plain pressed-state buttons; the handler keeps at most one chip on. */}
      <ToggleGroup type="multiple" aria-label="سبب الاستبعاد" spacing={2} className="w-full flex-wrap"
                   value={reason ? [reason] : []}
                   onValueChange={(v) => setReason(v.find((x) => x !== reason))}>
        {REJECT_REASONS.map((r) => (
          <ToggleGroupItem key={r} value={r} variant="outline"
                           className="h-11 rounded-full px-4 text-base data-[state=on]:border-primary data-[state=on]:bg-primary data-[state=on]:text-primary-foreground">
            {REASON_AR[r]}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      <div className="space-y-2">
        <Label htmlFor={noteId}>ملاحظة (اختياري)</Label>
        <Textarea id={noteId} value={note} maxLength={500} rows={3} onChange={(e) => setNote(e.target.value)} className="rounded-xl text-base" />
      </div>
      <div className="flex gap-2 pt-1 md:justify-end">
        <Button variant="outline" size="lg" onClick={submit}
                className="h-11 flex-1 border-destructive text-destructive hover:bg-destructive/10 hover:text-destructive md:flex-none md:px-8">
          استبعاد
        </Button>
        <Button variant="ghost" size="lg" onClick={() => onSubmit({})} className="h-11 flex-1 md:flex-none md:px-6">تخطي</Button>
      </div>
    </div>
  )
}

/** Why was this listing rejected? Bottom drawer on phone, centred dialog on tablet/desktop. */
export function RejectReasonSheet({ open, listingTitle, onSubmit, onCancel }: Props) {
  const bp = useBreakpoint()
  const change = (o: boolean) => { if (!o) onCancel() }
  const desc = listingTitle ? `سبب استبعاد: ${listingTitle}` : 'اختاروا السبب ليتعلّم التطبيق من اختياركم'
  if (bp === 'phone') {
    return (
      <Drawer open={open} onOpenChange={change}>
        <DrawerContent aria-modal="true" className="rounded-t-3xl pb-[env(safe-area-inset-bottom)]">
          <DrawerHeader>
            <DrawerTitle className="font-display text-lg font-bold">لماذا استبعدتم هذا العقار؟</DrawerTitle>
            <DrawerDescription>{desc}</DrawerDescription>
          </DrawerHeader>
          <Body onSubmit={onSubmit} />
        </DrawerContent>
      </Drawer>
    )
  }
  return (
    <Dialog open={open} onOpenChange={change}>
      <DialogContent aria-modal="true" showCloseButton={false} className="gap-5 rounded-3xl p-6 shadow-xl sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-display text-lg font-bold">لماذا استبعدتم هذا العقار؟</DialogTitle>
          <DialogDescription>{desc}</DialogDescription>
        </DialogHeader>
        <Body onSubmit={onSubmit} />
      </DialogContent>
    </Dialog>
  )
}
