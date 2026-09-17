import { useEffect, useMemo, useState } from 'react'
import {
  Button, Descriptions, Drawer, Empty, Segmented, Skeleton, Space, Tag, Typography,
} from 'antd'
import { FileTextOutlined, LinkOutlined, ProfileOutlined } from '@ant-design/icons'
import { fetchJob } from '../api'
import { sanitizeContent } from '../utils/sanitize'

const { Paragraph, Text } = Typography

/** 详情抽屉：按 id 拉取正文，默认按原站排版渲染，可切纯文本。 */
export default function JobDrawer({ job, open, onClose }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)
  const [mode, setMode] = useState('rich')

  useEffect(() => {
    if (!open || !job) return
    setLoading(true)
    setDetail(null)
    setMode('rich')
    fetchJob(job.id)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoading(false))
  }, [open, job])

  const html = useMemo(
    () => (detail?.content_html ? sanitizeContent(detail.content_html, detail.url) : ''),
    [detail],
  )

  const hasRich = Boolean(html)
  const hasText = Boolean(detail?.content)

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width={820}
      title={<span style={{ paddingRight: 24 }}>{job?.title}</span>}
      styles={{ body: { background: '#fff' } }}
      extra={
        <Space>
          {hasRich && hasText && (
            <Segmented
              size="small"
              value={mode}
              onChange={setMode}
              options={[
                { label: '排版', value: 'rich', icon: <ProfileOutlined /> },
                { label: '纯文本', value: 'text', icon: <FileTextOutlined /> },
              ]}
            />
          )}
          {job && (
            <Button icon={<LinkOutlined />} href={job.url} target="_blank" rel="noreferrer">
              原文
            </Button>
          )}
        </Space>
      }
    >
      {loading && <Skeleton active paragraph={{ rows: 12 }} />}

      {!loading && detail && (
        <>
          <Descriptions
            size="small"
            column={2}
            style={{ marginBottom: 20 }}
            items={[
              { key: 'date', label: '发布日期', children: detail.publish_date || '-' },
              {
                key: 'cat',
                label: '分类',
                children: detail.category ? <Tag>{detail.category}</Tag> : '-',
              },
              { key: 'site', label: '来源', children: detail.site },
              { key: 'sid', label: '站内 ID', children: <Text code>{detail.source_id}</Text> },
            ]}
          />

          {mode === 'rich' && hasRich && (
            <div className="detail-body" dangerouslySetInnerHTML={{ __html: html }} />
          )}

          {(mode === 'text' || !hasRich) && hasText && (
            <Paragraph style={{ whiteSpace: 'pre-wrap', lineHeight: 1.9, color: '#262626' }}>
              {detail.content}
            </Paragraph>
          )}

          {!hasRich && !hasText && (
            <Empty description="正文尚未抓取，可运行 jobspider backfill 补抓" />
          )}
        </>
      )}

      {!loading && !detail && <Empty description="加载失败" />}
    </Drawer>
  )
}
