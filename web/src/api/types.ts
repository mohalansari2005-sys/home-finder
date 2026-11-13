export type CommuteKind = 'school' | 'work' | 'university' | 'airport'
export type FamilyStatus = 'new' | 'seen' | 'bookmarked' | 'rejected' | 'visited'

export interface ListingCard {
  id: number; title: string | null; property_type: string | null; price: number | null; district: string | null
  bedrooms: number | null; bathrooms: number | null; built_area_m2: number | null; land_area_m2: number | null
  photo_url: string | null; score: number | null; commutes: Partial<Record<CommuteKind, number | null>>
  family_status: FamilyStatus; first_seen: string | null; lat: number | null; lng: number | null
  price_drop: { from: number; to: number; at: string } | null
  /** 'active' | 'removed' (any other value is treated as normal) */
  status: string
}
export interface ListingDetail extends ListingCard {
  description: string | null; livings: number | null; building_age_years: number | null; street_width_m: number | null
  facing: string | null; street_count: number | null; deed_type: string | null; has_maid_room: boolean | null
  has_driver_room: boolean | null; has_yard: boolean | null; has_elevator: boolean | null; geo_precision: string
  photos: string[]; sources: { source: string; url: string; seller_phone: string | null; seller_name: string | null }[]
  price_history: { price: number; observed_at: string }[]; score_breakdown: ScoreBreakdown | null
  passes_filters: boolean; filter_reasons: string[]
}
export interface ScoreContribution { factor: string; value: number; weight: number; delta: number }
export interface ScoreBreakdown { total: number | null; contributions: ScoreContribution[]; missing: string[] }
export interface FeedPage { items: ListingCard[]; next_offset: number | null }
export interface MapPoint {
  id: number; lat: number; lng: number; price: number | null; score: number | null; family_status: FamilyStatus
  title: string | null; district: string | null; photo_url: string | null
}
export type PlaceKind = CommuteKind | 'home'
export interface Place { kind: PlaceKind; name: string; lat: number; lng: number }
export interface HardFilters {
  city?: string; property_types?: string[]; districts?: string[]; price_max?: number | null; min_bedrooms?: number | null
  max_commute?: Partial<Record<CommuteKind, number>>; building_age_max?: number | null; street_width_min?: number | null
}
export interface Preferences {
  hard_filters: HardFilters; weights: Record<string, number>; targets: Record<string, unknown>; locked_weights: string[]
  defaults: { weights: Record<string, number>; targets: Record<string, unknown> }
}
export interface PreferencePatch {
  hard_filters?: Record<string, unknown>; weights?: Record<string, number>; targets?: Record<string, unknown>
  unlock?: string[]; reset_weights?: boolean
}
export interface PreferenceChange {
  at: string; source: 'user' | 'learner' | 'agent'; diff: Record<string, { from: unknown; to: unknown }>; explanation: string
}
export interface SystemStatus {
  worker: { online: boolean; last_seen: string | null; hostname: string | null; current_job_id: number | null }
  jobs: { pending: number; claimed: number; failed: number }
  counts: { active: number; new: number; bookmarked: number; rejected: number; passing: number }
  adapters: { source: string; status: string; reason: string | null; last_success_at: string | null; last_scrape_at: string | null }[]
  failed_jobs: { id: number; type: string; error: string | null; finished_at: string | null }[]
}
export type FeedView = 'all' | 'new' | 'bookmarked'
export type ReactKind = 'bookmark' | 'reject' | 'unreject'
export interface Suggestion { code: string; reason: string; count: number; patch: { hard_filters: Record<string, unknown> }; text: string }
export interface ReactExtra { reason_code?: string | null; note?: string | null }

// ---- visits (M5) ----
export type ContactStatus = 'not_contacted' | 'contacted' | 'confirmed' | 'visited' | 'cancelled'
export type TripStatus = 'planned' | 'done' | 'cancelled'
export type TripOrigin = 'home' | 'school' | 'work' | 'university'
export interface VisitGroup {
  key: string; districts: string[]; listing_ids: number[]; count: number; avg_score: number | null
  centroid: [number, number]; listings: ListingCard[]
}
export interface VisitGroups { groups: VisitGroup[]; no_location: ListingCard[] }
export interface TripStop {
  id: number; position: number; listing: ListingCard
  eta_local: string | null; etd_local: string | null; drive_min: number | null
  contact_status: ContactStatus; rating: number | null; notes: string | null
  /** subset of "removed" | "price_changed"; unknown values are ignored */
  flags: string[]; old_price?: number | null
  whatsapp_url: string | null; phone: string | null; photos: string[]
  /** the listing's source-site URL when the server provides it (not in the original contract) */
  source_url?: string | null
}
export interface Trip {
  id: number; title: string; date: string; start_time: string; origin_kind: TripOrigin; minutes_per_visit: number
  status: TripStatus
  /** "no_route" | "skipped_no_location" | "precheck_pending"; unknown codes are ignored */
  warnings: string[]
  skipped_no_location?: number
  total_drive_min: number | null; maps_url: string; stops: TripStop[]
}
export interface TripCreate {
  listing_ids: number[]; date: string; start_time: string; origin_kind: TripOrigin; minutes_per_visit: number; title?: string
}
export interface StopPatch { contact_status?: ContactStatus; rating?: number; notes?: string }
