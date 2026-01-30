import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
})

export interface Event {
  id: number
  uuid: string
  title: string
  city: string
  source: string
  date_start: string | null
  date_end: string | null
  is_active: boolean
  category: string[] | null
}

export interface EtlRun {
  id: number
  run_type: string
  source: string | null
  status: string
  staging_count: number
  inserted_count: number
  updated_count: number
  unchanged_count: number
  started_at: string
  duration_seconds: number | null
}

export interface EtlError {
  id: number
  error_type: string
  source: string | null
  json_file: string | null
  error_message: string | null
  created_at: string
}

export interface DashboardStats {
  total_events: number
  active_events: number
  events_by_city: Record<string, number>
  events_by_source: Record<string, number>
  recent_etl_runs: EtlRun[]
  staging_count: number
}

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export const fetchDashboard = async (): Promise<DashboardStats> => {
  const { data } = await api.get('/dashboard/')
  return data
}

export const fetchEvents = async (params: Record<string, string>): Promise<PaginatedResponse<Event>> => {
  const { data } = await api.get('/events/', { params })
  return data
}

export const fetchEtlRuns = async (params: Record<string, string>): Promise<PaginatedResponse<EtlRun>> => {
  const { data } = await api.get('/etl-runs/', { params })
  return data
}

export const fetchEtlErrors = async (params: Record<string, string>): Promise<PaginatedResponse<EtlError>> => {
  const { data } = await api.get('/etl-errors/', { params })
  return data
}

export const fetchCities = async (): Promise<{ city: string; count: number }[]> => {
  const { data } = await api.get('/events/cities/')
  return data
}

export const fetchSources = async (): Promise<{ source: string; count: number }[]> => {
  const { data } = await api.get('/events/sources/')
  return data
}

export default api
