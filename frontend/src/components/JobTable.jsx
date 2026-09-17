import { Button, Space, Table, Tag, Typography } from 'antd'
import { LinkOutlined } from '@ant-design/icons'

const { Text } = Typography

const CATEGORY_COLOR = {
  专题专栏: 'geekblue',
  考试公告: 'green',
  新闻资讯: 'orange',
  企业招聘: 'purple',
}

/** 公告列表。点击标题打开详情抽屉。 */
export default function JobTable({ data, loading, page, size, total, onPageChange, onOpen }) {
  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      render: (title, row) => (
        <a onClick={() => onOpen(row)} style={{ fontWeight: 500 }}>{title}</a>
      ),
    },
    {
      title: '分类',
      dataIndex: 'category',
      width: 110,
      render: (c) => (c ? <Tag color={CATEGORY_COLOR[c] || 'default'}>{c}</Tag> : '-'),
    },
    {
      title: '发布日期',
      dataIndex: 'publish_date',
      width: 120,
      render: (d) => <Text type="secondary">{d || '-'}</Text>,
    },
    {
      title: '来源',
      dataIndex: 'site',
      width: 110,
      render: (s) => <Text type="secondary">{s}</Text>,
    },
    {
      title: '操作',
      width: 90,
      render: (_, row) => (
        <Space size={4}>
          <Button type="link" size="small" icon={<LinkOutlined />}
                  href={row.url} target="_blank" rel="noreferrer">
            原文
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <Table
      rowKey="id"
      size="middle"
      loading={loading}
      dataSource={data}
      columns={columns}
      pagination={{
        current: page,
        pageSize: size,
        total,
        showSizeChanger: true,
        pageSizeOptions: [20, 50, 100],
        showTotal: (t) => `共 ${t} 条`,
        onChange: onPageChange,
      }}
    />
  )
}
