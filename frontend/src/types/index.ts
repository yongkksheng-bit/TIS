// TypeScript types mirroring backend Pydantic schemas

export type ProjectStatus =
  | 'uploaded' | 'parsing' | 'parsed' | 'evaluating'
  | 'evaluation_ready' | 'worthy' | 'unworthy' | 'generating_documents'
  | 'awaiting_pricing' | 'awaiting_review' | 'completed' | 'terminated_by_boss'

export interface Project {
  id: number
  project_name: string
  project_type: string
  owner_unit: string
  region: string
  budget_amount: number
  status: ProjectStatus
  relationship_flag: boolean
  generation_mode: string
  bid_open_date: string
  created_at?: string
}

export interface BidOutcome {
  id: number
  project_id: number
  outcome_status: 'win' | 'lose' | 'disqualified' | 'abandoned' | 'withdrawn'
  final_bid_price: number
  winning_price?: number
  review_analysis?: Record<string, unknown>
}

export interface RebidAlert {
  is_rebid: boolean
  historical_project_id?: number
  historical_outcome?: string
  warnings: string[]
  revivable_drafts?: unknown[]
}
