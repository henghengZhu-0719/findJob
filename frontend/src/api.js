/** 后端接口封装。开发环境经 vite 代理，生产环境同源。 */
const BASE = '/api/jobs'

async function request(url) {
  const res = await fetch(url)
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.detail || `请求失败 ${res.status}`)
  }
  return res.json()
}

export function fetchJobs(params) {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') qs.append(k, v)
  })
  return request(`${BASE}?${qs}`)
}

export const fetchJob = (id) => request(`${BASE}/${id}`)
export const fetchFacets = () => request(`${BASE}/facets`)
export const fetchStats = () => request(`${BASE}/stats`)
