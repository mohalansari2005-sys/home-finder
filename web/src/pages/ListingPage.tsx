import { useNavigate, useParams } from 'react-router'
import { ChevronRight } from 'lucide-react'
import { ListingDetailView } from '../components/ListingDetailView'
import { Button } from '@/components/ui/button'

export function ListingPage() {
  const { id } = useParams()
  const nav = useNavigate()
  return (
    <div className="mx-auto max-w-3xl">
      <Button variant="outline" onClick={() => nav(-1)} className="m-4 mb-0">
        {/* chevron points to the right = "back" in RTL; flipped in LTR */}
        <ChevronRight aria-hidden className="ltr:-scale-x-100" strokeWidth={1.75} />
        رجوع
      </Button>
      <ListingDetailView id={Number(id)} />
    </div>
  )
}
