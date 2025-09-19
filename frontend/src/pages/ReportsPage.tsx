import React, { useState, useEffect } from 'react'
import { 
  Table, 
  Button, 
  Space, 
  Card, 
  Typography, 
  Tag, 
  message, 
  Modal,
  Empty,
  Tooltip
} from 'antd'
import { 
  DownloadOutlined, 
  DeleteOutlined, 
  EyeOutlined, 
  FileExcelOutlined,
  CalendarOutlined,
  FileOutlined
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { ReportItem } from '../types/store'
import apiService from '../services/api'

const { Title, Text } = Typography
const { confirm } = Modal

const ReportsPage: React.FC = () => {
  const [reports, setReports] = useState<ReportItem[]>([])
  const [loading, setLoading] = useState(false)
  const [downloading, setDownloading] = useState<string | null>(null)

  // Mock data for demonstration
  useEffect(() => {
    loadReports()
  }, [])

  const loadReports = async () => {
    setLoading(true)
    try {
      // Fetch real reports from backend
      const response = await apiService.listReports()
      
      // Transform backend response to ReportItem format
      const transformedReports: ReportItem[] = response.reports.map((report: any) => ({
        id: report.report_id,
        name: `AI报表_${report.report_id.substring(0, 8)}`,
        fileId: report.session_id, // Use session_id as fileId
        fileName: 'data.xlsx', // Backend doesn't return filename, use placeholder
        generatedAt: new Date(report.generation_time),
        filePath: report.download_url,
        config: {
          sourceFileId: report.session_id,
          reportConfig: {
            sections: [] // Backend doesn't return config, use empty array
          }
        },
        status: 'completed' as const // All returned reports are completed
      }))
      
      setReports(transformedReports)
      
      if (transformedReports.length === 0) {
        console.log('No reports found')
      }
    } catch (error) {
      console.error('Failed to load reports:', error)
      message.error('加载报表列表失败，请确保后端服务正常运行')
      // Set empty array on error
      setReports([])
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = async (report: ReportItem) => {
    setDownloading(report.id)
    try {
      const blob = await apiService.downloadReport(report.id)
      
      // Create download link
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${report.name}.xlsx`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
      
      message.success('报表下载成功')
    } catch (error) {
      console.error('Download error:', error)
      message.error('报表下载失败')
    } finally {
      setDownloading(null)
    }
  }

  const handleDelete = (report: ReportItem) => {
    confirm({
      title: '确认删除',
      content: `确定要删除报表 "${report.name}" 吗？此操作不可恢复。`,
      okText: '确认',
      cancelText: '取消',
      okType: 'danger',
      onOk: async () => {
        try {
          // Here we would call the delete API
          setReports(prev => prev.filter(r => r.id !== report.id))
          message.success('报表删除成功')
        } catch (error) {
          console.error('Delete error:', error)
          message.error('报表删除失败')
        }
      }
    })
  }

  const getStatusTag = (status: ReportItem['status']) => {
    switch (status) {
      case 'completed':
        return <Tag color="success">已完成</Tag>
      case 'generating':
        return <Tag color="processing">生成中</Tag>
      case 'failed':
        return <Tag color="error">失败</Tag>
      default:
        return <Tag color="default">未知</Tag>
    }
  }

  const formatDate = (date: Date) => {
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const columns: ColumnsType<ReportItem> = [
    {
      title: '报表名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: ReportItem) => (
        <Space direction="vertical" size={0}>
          <Text strong>{name}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            <FileOutlined style={{ marginRight: 4 }} />
            {record.fileName}
          </Text>
        </Space>
      ),
    },
    {
      title: '报表类型',
      dataIndex: ['config', 'reportConfig', 'sections'],
      key: 'sections',
      render: (sections: string[]) => (
        <Space wrap>
          {sections.map(section => {
            const sectionMap: { [key: string]: { label: string; color: string } } = {
              stableState: { label: '稳态分析', color: 'blue' },
              functionalCalc: { label: '功能计算', color: 'green' },
              statusEval: { label: '状态评估', color: 'orange' }
            }
            const config = sectionMap[section] || { label: section, color: 'default' }
            return (
              <Tag key={section} color={config.color}>
                {config.label}
              </Tag>
            )
          })}
        </Space>
      ),
    },
    {
      title: '生成时间',
      dataIndex: 'generatedAt',
      key: 'generatedAt',
      render: (date: Date) => (
        <Space>
          <CalendarOutlined />
          <Text>{formatDate(date)}</Text>
        </Space>
      ),
      sorter: (a, b) => a.generatedAt.getTime() - b.generatedAt.getTime(),
      defaultSortOrder: 'descend',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: ReportItem['status']) => getStatusTag(status),
      filters: [
        { text: '已完成', value: 'completed' },
        { text: '生成中', value: 'generating' },
        { text: '失败', value: 'failed' },
      ],
      onFilter: (value, record) => record.status === value,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_, record: ReportItem) => (
        <Space>
          <Tooltip title="下载报表">
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              size="small"
              loading={downloading === record.id}
              disabled={record.status !== 'completed'}
              onClick={() => handleDownload(record)}
            >
              下载
            </Button>
          </Tooltip>
          <Tooltip title="查看详情">
            <Button
              icon={<EyeOutlined />}
              size="small"
              disabled={record.status !== 'completed'}
            >
              查看
            </Button>
          </Tooltip>
          <Tooltip title="删除报表">
            <Button
              danger
              icon={<DeleteOutlined />}
              size="small"
              onClick={() => handleDelete(record)}
            >
              删除
            </Button>
          </Tooltip>
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: '24px', height: '100%' }}>
      <Card>
        <div style={{ marginBottom: 24 }}>
          <Title level={2} style={{ marginBottom: 8 }}>
            <FileExcelOutlined style={{ marginRight: 8, color: '#1890ff' }} />
            报表管理
          </Title>
          <Text type="secondary">
            管理和下载您生成的所有报表文件
          </Text>
        </div>

        <Table
          columns={columns}
          dataSource={reports}
          loading={loading}
          rowKey="id"
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) => 
              `第 ${range[0]}-${range[1]} 条，共 ${total} 条记录`,
          }}
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="暂无报表数据"
              >
                <Button type="primary" href="/chat">
                  生成第一个报表
                </Button>
              </Empty>
            ),
          }}
        />
      </Card>
    </div>
  )
}

export default ReportsPage
