import { useCallback, useEffect, useState } from 'react'
import { App as AntApp, Layout, Typography } from 'antd'
import FilterBar from './components/FilterBar'
import JobTable from './components/JobTable'
import JobDrawer from './components/JobDrawer'
import StatsBar from './components/StatsBar'
import { fetchFacets, fetchJobs, fetchStats } from './api'

const { Header, Content } = Layout
const { Title, Text } = Typography

const EMPTY_FILTER = { q: '', site: undefined, category: undefined, dates: null }

export default function App() {
  const { message } = AntApp.useApp()
  const [filter, setFilter] = useState(EMPTY_FILTER)
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(20)
  const [data, setData] = useState({ items: [], total: 0 })
  const [loading, setLoading] = useState(false)
  const [facets, setFacets] = useState({ sites: [], categories: [] })
  const [stats, setStats] = useState([])
  const [current, setCurrent] = useState(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  const load = useCallback(async (p = page, s = size, f = filter) => {
    setLoading(true)
    try {
      const [from, to] = f.dates || []
      const res = await fetchJobs({
        q: f.q,
        site: f.site,
        category: f.category,
        date_from: from?.format('YYYY-MM-DD'),
        date_to: to?.format('YYYY-MM-DD'),
        page: p,
        size: s,
      })
      setData(res)
    } catch (e) {
      message.error(e.message)
    } finally {
      setLoading(false)
    }
  }, [page, size, filter, message])

  useEffect(() => {
    load(1, size, filter)
    fetchFacets().then(setFacets).catch(() => {})
    fetchStats().then(setStats).catch(() => {})
    // 仅首屏加载一次
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSearch = () => { setPage(1); load(1, size, filter) }
  const handleReset = () => {
    setFilter(EMPTY_FILTER); setPage(1); load(1, size, EMPTY_FILTER)
  }
  const handlePageChange = (p, s) => { setPage(p); setSize(s); load(p, s, filter) }
  const handleOpen = (row) => { setCurrent(row); setDrawerOpen(true) }

  return (
    <Layout style={{ minHeight: '100vh', background: '#f5f6f8' }}>
      <Header style={{ background: '#fff', borderBottom: '1px solid #f0f0f0', padding: '0 24px' }}>
        <Title level={4} style={{ margin: 0, lineHeight: '64px' }}>
          findJob <Text type="secondary" style={{ fontSize: 14, fontWeight: 400 }}>招聘公告聚合</Text>
        </Title>
      </Header>
      <Content style={{ padding: 24, maxWidth: 1200, width: '100%', margin: '0 auto' }}>
        <StatsBar stats={stats} />
        <FilterBar
          value={filter}
          facets={facets}
          loading={loading}
          onChange={setFilter}
          onSearch={handleSearch}
          onReset={handleReset}
        />
        <JobTable
          data={data.items}
          loading={loading}
          page={page}
          size={size}
          total={data.total}
          onPageChange={handlePageChange}
          onOpen={handleOpen}
        />
      </Content>
      <JobDrawer job={current} open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </Layout>
  )
}
