import React from 'react'
import { Button, Space, Tag, Divider } from 'antd'
import { 
  UserOutlined, 
  RobotOutlined, 
  FileOutlined, 
  DownloadOutlined,
  SettingOutlined
} from '@ant-design/icons'
import { Message } from '../../types/store'

interface MessageBubbleProps {
  message: Message
  isLoading?: boolean
  onActionClick?: (action: string) => void
  onDownloadReport?: (reportId: string) => void
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ 
  message, 
  isLoading = false,
  onActionClick,
  onDownloadReport
}) => {
  const isUser = message.type === 'user'
  const isSystem = message.type === 'system'

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('zh-CN', { 
      hour: '2-digit', 
      minute: '2-digit' 
    })
  }

  const renderMessageContent = () => {
    // Handle file upload messages (both system and regular messages)
    if (message.metadata?.fileInfo) {
      const fileInfo = message.metadata.fileInfo
      console.log('[MessageBubble] 文件信息:', fileInfo)
      console.log('[MessageBubble] channelStats:', message.metadata?.channelStats)
      
      return (
        <div>
          <div className="system-message">
            <Tag color="blue">{message.content}</Tag>
          </div>
          <Divider style={{ margin: '8px 0' }} />
          <div className="file-attachment">
            <FileOutlined style={{ color: '#1890ff', marginRight: 8 }} />
            <span><strong>{fileInfo.filename}</strong></span>
            <span className="file-details">
              ({fileInfo.file_size > 1024 * 1024 
                ? `${(fileInfo.file_size / (1024 * 1024)).toFixed(2)} MB`
                : `${(fileInfo.file_size / 1024).toFixed(1)} KB`
              })
            </span>
          </div>
          
          {/* 显示通道统计信息 */}
          {message.metadata?.channelStats && message.metadata.channelStats.length > 0 && (
            <div className="channel-stats" style={{ marginTop: 12, fontSize: '13px' }}>
              <div style={{ fontWeight: 'bold', marginBottom: 8, color: '#1890ff' }}>
                📊 检测到 {message.metadata.channelStats.length} 个数据通道：
              </div>
              <div style={{ 
                maxHeight: '200px', 
                overflowY: 'auto',
                background: '#f5f5f5',
                padding: '8px',
                borderRadius: '4px'
              }}>
                {message.metadata.channelStats.map((ch: any, idx: number) => {
                  const totalChannels = message.metadata?.channelStats?.length || 0
                  return (
                  <div key={idx} style={{ 
                    marginBottom: idx < totalChannels - 1 ? '8px' : 0,
                    paddingBottom: idx < totalChannels - 1 ? '8px' : 0,
                    borderBottom: idx < totalChannels - 1 ? '1px solid #e0e0e0' : 'none'
                  }}>
                    <div style={{ fontWeight: 'bold', color: '#333' }}>
                      {idx + 1}. {ch.name} {ch.unit && `(${ch.unit})`}
                    </div>
                    <div style={{ color: '#666', fontSize: '12px', marginTop: 4 }}>
                      样本数: {ch.sample_count} | 
                      最小值: {ch.min_value.toFixed(3)} | 
                      最大值: {ch.max_value.toFixed(3)} | 
                      平均值: {ch.avg_value.toFixed(3)} | 
                      标准差: {ch.std_value.toFixed(3)}
                    </div>
                  </div>
                )}
                )}
              </div>
            </div>
          )}
          
          {/* 如果没有统计信息，显示通道列表 */}
          {!message.metadata?.channelStats && fileInfo.available_channels && fileInfo.available_channels.length > 0 && (
            <div className="available-channels">
              <div style={{ marginTop: 8, fontSize: '12px', color: '#666' }}>
                可用通道: {fileInfo.available_channels.slice(0, 5).join(', ')}
                {fileInfo.available_channels.length > 5 && ` 等${fileInfo.available_channels.length}个`}
              </div>
            </div>
          )}
        </div>
      )
    }

    // Handle system messages without file info
    if (isSystem) {
      return (
        <div className="system-message">
          <Tag color="blue">{message.content}</Tag>
        </div>
      )
    }

    // Handle report generation messages
    if (message.metadata?.reportId) {
      return (
        <div>
          <div>{message.content}</div>
          <Divider style={{ margin: '8px 0' }} />
          <div className="report-actions">
            <Button 
              type="primary" 
              size="small"
              icon={<DownloadOutlined />}
              onClick={() => onDownloadReport?.(message.metadata!.reportId!)}
            >
              下载报表
            </Button>
          </div>
        </div>
      )
    }

    // Regular message content
    return message.content
  }

  const renderSuggestedActions = () => {
    if (!message.metadata?.suggestedActions || message.metadata.suggestedActions.length === 0) {
      return null
    }

    return (
      <div className="suggested-actions">
        <div style={{ fontSize: '12px', color: '#666', marginBottom: 4 }}>
          建议操作:
        </div>
        <Space wrap>
          {message.metadata.suggestedActions.map((action, index) => (
            <Button
              key={index}
              size="small"
              type="dashed"
              onClick={() => onActionClick?.(action)}
            >
              {action}
            </Button>
          ))}
        </Space>
      </div>
    )
  }

  const renderConfigInfo = () => {
    if (!message.metadata?.reportConfig) {
      return null
    }

    const config = message.metadata.reportConfig
    return (
      <div className="config-info">
        <Divider style={{ margin: '8px 0' }} />
        <div style={{ fontSize: '12px', color: '#666', marginBottom: 4 }}>
          <SettingOutlined style={{ marginRight: 4 }} />
          配置信息:
        </div>
        <div style={{ fontSize: '12px', color: '#888' }}>
          报表类型: {config.reportConfig.sections.join(', ')}
        </div>
      </div>
    )
  }

  return (
    <div className={`message-item ${isUser ? 'user-message' : 'ai-message'} ${isSystem ? 'system-message' : ''}`}>
      <div className="message-avatar">
        {isUser ? <UserOutlined /> : <RobotOutlined />}
      </div>
      
      <div className="message-content">
        <div className="message-text">
          {renderMessageContent()}
        </div>
        
        {renderConfigInfo()}
        {renderSuggestedActions()}
        
        <div className="message-metadata">
          <span className="message-time">{formatTime(message.timestamp)}</span>
          {isLoading && <span className="loading-indicator">发送中...</span>}
        </div>
      </div>
    </div>
  )
}

export default MessageBubble
