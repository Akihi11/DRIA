import React from 'react'
import { Button, Space, Tag } from 'antd'
import { 
  UserOutlined, 
  RobotOutlined
} from '@ant-design/icons'
import { Message } from '../../types/store'
import FileAnalysisResult from '../FileAnalysis/FileAnalysisResult'

interface MessageBubbleProps {
  message: Message
  isLoading?: boolean
  onActionClick?: (action: string) => void
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ 
  message, 
  isLoading = false,
  onActionClick
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
    // Handle system messages with file analysis
    if (isSystem && message.metadata?.fileInfo?.analysis?.success) {
      const fileInfo = message.metadata.fileInfo
      const analysis = fileInfo.analysis
      
      return (
        <FileAnalysisResult
          filename={fileInfo.filename}
          fileSize={fileInfo.file_size}
          channels={analysis.channels}
          totalChannels={analysis.total_channels}
          timestamp={message.timestamp}
        />
      )
    }

    // Handle regular system messages
    if (isSystem) {
      return (
        <div className="system-message">
          <Tag color="blue">{message.content}</Tag>
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

  // 如果是系统消息且有文件分析结果，不显示头像和时间戳
  if (isSystem && message.metadata?.fileInfo?.analysis?.success) {
    return (
      <div className="message-item system-message">
        <div className="message-content">
          {renderMessageContent()}
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