import React, { useState } from 'react'
import { Button, Space, Tag, message as antdMessage } from 'antd'
import { 
  UserOutlined, 
  RobotOutlined,
  DownloadOutlined
} from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import { Message } from '../../types/store'
import FileAnalysisResult from '../FileAnalysis/FileAnalysisResult'
import apiService from '../../services/api'

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
  const [downloading, setDownloading] = useState(false)

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('zh-CN', { 
      hour: '2-digit', 
      minute: '2-digit' 
    })
  }

  const handleDownloadReport = async (reportId: string) => {
    setDownloading(true)
    try {
      const blob = await apiService.downloadSteadyStateReport(reportId)
      
      // Create download link
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `steady_state_report_${reportId}.xlsx`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
      
      antdMessage.success('报表下载成功')
    } catch (error) {
      console.error('Download error:', error)
      antdMessage.error('报表下载失败')
    } finally {
      setDownloading(false)
    }
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

    // Regular message content - render as markdown
    return (
      <ReactMarkdown
        components={{
          // 自定义样式
          p: ({ children }) => <p style={{ margin: '0.5em 0', lineHeight: '1.6' }}>{children}</p>,
          code: ({ children, className }) => {
            const isInline = !className
            return isInline ? (
              <code style={{ 
                background: '#f5f5f5', 
                padding: '2px 6px', 
                borderRadius: '3px',
                fontFamily: 'monospace',
                fontSize: '0.9em'
              }}>{children}</code>
            ) : (
              <pre style={{
                background: '#f5f5f5',
                padding: '12px',
                borderRadius: '4px',
                overflow: 'auto',
                margin: '0.5em 0'
              }}>
                <code className={className} style={{ 
                  fontFamily: 'monospace',
                  fontSize: '0.9em'
                }}>{children}</code>
              </pre>
            )
          },
          ul: ({ children }) => <ul style={{ margin: '0.5em 0', paddingLeft: '20px' }}>{children}</ul>,
          ol: ({ children }) => <ol style={{ margin: '0.5em 0', paddingLeft: '20px' }}>{children}</ol>,
          li: ({ children }) => <li style={{ margin: '0.25em 0', lineHeight: '1.6' }}>{children}</li>,
          strong: ({ children }) => <strong style={{ fontWeight: 'bold' }}>{children}</strong>,
          em: ({ children }) => <em style={{ fontStyle: 'italic' }}>{children}</em>,
          h1: ({ children }) => <h1 style={{ fontSize: '1.5em', margin: '0.8em 0 0.5em 0', fontWeight: 'bold' }}>{children}</h1>,
          h2: ({ children }) => <h2 style={{ fontSize: '1.3em', margin: '0.8em 0 0.5em 0', fontWeight: 'bold' }}>{children}</h2>,
          h3: ({ children }) => <h3 style={{ fontSize: '1.1em', margin: '0.8em 0 0.5em 0', fontWeight: 'bold' }}>{children}</h3>,
          blockquote: ({ children }) => (
            <blockquote style={{ 
              borderLeft: '4px solid #ddd', 
              paddingLeft: '1em', 
              margin: '0.5em 0',
              color: '#666',
              fontStyle: 'italic'
            }}>{children}</blockquote>
          ),
          a: ({ children, href }) => (
            <a 
              href={href} 
              target="_blank" 
              rel="noopener noreferrer"
              style={{ 
                color: '#1890ff',
                textDecoration: 'none'
              }}
            >
              {children}
            </a>
          ),
          hr: () => <hr style={{ border: 'none', borderTop: '1px solid #e8e8e8', margin: '1em 0' }} />,
        }}
      >
        {message.content || ''}
      </ReactMarkdown>
    )
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

  const renderDownloadButton = () => {
    const reportId = message.metadata?.reportId || message.metadata?.currentParams?.report_id
    
    if (!reportId) {
      return null
    }

    return (
      <div style={{ marginTop: 8 }}>
        <Button
          type="primary"
          icon={<DownloadOutlined />}
          onClick={() => handleDownloadReport(reportId)}
          loading={downloading}
          size="small"
        >
          下载报表
        </Button>
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
        {renderDownloadButton()}
        
        <div className="message-metadata">
          <span className="message-time">{formatTime(message.timestamp)}</span>
          {isLoading && <span className="loading-indicator">发送中...</span>}
        </div>
      </div>
    </div>
  )
}

export default MessageBubble