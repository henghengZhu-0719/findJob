import { Button, Card, Col, DatePicker, Input, Row, Select, Space } from 'antd'
import { ReloadOutlined, SearchOutlined } from '@ant-design/icons'

const { RangePicker } = DatePicker

/** 查询条件区。受控组件，状态由 App 持有。 */
export default function FilterBar({ value, facets, loading, onChange, onSearch, onReset }) {
  const set = (patch) => onChange({ ...value, ...patch })

  return (
    <Card size="small" style={{ marginBottom: 16 }}>
      <Row gutter={[12, 12]} align="middle">
        <Col xs={24} md={8}>
          <Input
            allowClear
            prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
            placeholder="标题关键词，如：教师 / 辅警"
            value={value.q}
            onChange={(e) => set({ q: e.target.value })}
            onPressEnter={onSearch}
          />
        </Col>
        <Col xs={12} md={4}>
          <Select
            allowClear
            style={{ width: '100%' }}
            placeholder="站点"
            value={value.site || undefined}
            options={facets.sites.map((s) => ({ label: s, value: s }))}
            onChange={(v) => set({ site: v })}
          />
        </Col>
        <Col xs={12} md={4}>
          <Select
            allowClear
            style={{ width: '100%' }}
            placeholder="分类"
            value={value.category || undefined}
            options={facets.categories.map((c) => ({ label: c, value: c }))}
            onChange={(v) => set({ category: v })}
          />
        </Col>
        <Col xs={24} md={8}>
          <Space.Compact style={{ width: '100%' }}>
            <RangePicker
              style={{ width: '100%' }}
              value={value.dates}
              onChange={(d) => set({ dates: d })}
            />
          </Space.Compact>
        </Col>
      </Row>
      <Row justify="end" style={{ marginTop: 12 }}>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={onReset}>重置</Button>
          <Button type="primary" icon={<SearchOutlined />} loading={loading} onClick={onSearch}>
            查询
          </Button>
        </Space>
      </Row>
    </Card>
  )
}
