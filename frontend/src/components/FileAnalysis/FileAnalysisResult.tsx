import React from 'react'
import { Card, Typography, Divider, Space } from 'antd'
import { FileTextOutlined, BarChartOutlined } from '@ant-design/icons'

const { Text, Title } = Typography

interface ChannelData {
  channel_name: string
  count: number
  mean: number
  max_value: number
  min_value: number
  std_dev: number
}

interface FileAnalysisResultProps {
  filename: string
  fileSize?: number
  channels: ChannelData[]
  totalChannels: number
  timestamp: Date
}

const FileAnalysisResult: React.FC<FileAnalysisResultProps> = ({
  filename,
  fileSize,
  channels,
  totalChannels,
  timestamp
}) => {
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    const size = parseFloat((bytes / Math.pow(k, i)).toFixed(2))
    return size + sizes[i]
  }

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('zh-CN', { 
      hour: '2-digit', 
      minute: '2-digit' 
    })
  }

  return (
    <Card 
      style={{ 
        margin: '8px 0',
        borderRadius: '8px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
      }}
      bodyStyle={{ padding: '16px' }}
    >
      {/* 顶部成功消息 */}
      <div style={{ marginBottom: '12px' }}>
        <Text style={{ color: '#1890ff', fontSize: '14px', fontWeight: 'bold' }}>
          文件"{filename}" 上传成功! 检测到{totalChannels}个数据通道。
        </Text>
      </div>

      {/* 文件信息 */}
      <div style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <FileTextOutlined style={{ color: '#666' }} />
        <Text style={{ fontSize: '13px', color: '#666' }}>
          {filename}
        </Text>
        {fileSize && (
          <Text style={{ fontSize: '12px', color: '#999', marginLeft: '4px' }}>
            ({formatFileSize(fileSize)})
          </Text>
        )}
      </div>

      {/* 通道标题 */}
      <div style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <BarChartOutlined style={{ color: '#1890ff' }} />
        <Text style={{ color: '#1890ff', fontSize: '13px', fontWeight: 'bold' }}>
          检测到{totalChannels}个数据通道:
        </Text>
      </div>

      {/* 通道列表 */}
      <div style={{ marginBottom: '12px' }}>
        {channels.map((channel, index) => (
          <div key={channel.channel_name} style={{ marginBottom: '8px' }}>
            <div style={{ marginBottom: '4px' }}>
              <Text style={{ fontSize: '13px', fontWeight: 'bold' }}>
                {index + 1}. {channel.channel_name}
              </Text>
            </div>
            <div style={{ fontSize: '12px', color: '#666', lineHeight: '1.4' }}>
              样本数: {channel.count} | 
              最小值: {channel.min_value.toFixed(3)} | 
              最大值: {channel.max_value.toFixed(3)} | 
              平均值: {channel.mean.toFixed(3)} | 
              标准差: {channel.std_dev.toFixed(3)}
            </div>
            {index < channels.length - 1 && (
              <Divider style={{ margin: '6px 0', backgroundColor: '#f0f0f0' }} />
            )}
          </div>
        ))}
      </div>

      {/* 底部时间戳 */}
      <div style={{ textAlign: 'left' }}>
        <Text style={{ fontSize: '12px', color: '#999' }}>
          {formatTime(timestamp)}
        </Text>
      </div>
    </Card>
  )
}

export default FileAnalysisResult
