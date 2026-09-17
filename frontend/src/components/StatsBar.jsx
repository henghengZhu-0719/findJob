import { Card, Col, Row, Statistic } from 'antd'
import { DatabaseOutlined, FieldTimeOutlined } from '@ant-design/icons'

/** 顶部统计：各站点入库量与数据日期跨度。 */
export default function StatsBar({ stats }) {
  if (!stats.length) return null
  const total = stats.reduce((n, s) => n + s.total, 0)
  const latest = stats.map((s) => s.latest).filter(Boolean).sort().pop()

  return (
    <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
      <Col xs={12} md={6}>
        <Card size="small">
          <Statistic title="入库公告" value={total} prefix={<DatabaseOutlined />} />
        </Card>
      </Col>
      <Col xs={12} md={6}>
        <Card size="small">
          <Statistic title="最新发布" value={latest || '-'} prefix={<FieldTimeOutlined />} />
        </Card>
      </Col>
      {stats.map((s) => (
        <Col xs={12} md={6} key={s.site}>
          <Card size="small">
            <Statistic title={s.site} value={s.total} suffix="条" />
          </Card>
        </Col>
      ))}
    </Row>
  )
}
