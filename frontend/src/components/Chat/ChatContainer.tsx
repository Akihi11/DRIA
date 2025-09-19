import React, { useState, useRef, useEffect, forwardRef, useImperativeHandle } from 'react'
import { Layout, Input, Button, Upload, message, Space, Spin } from 'antd'
import { 
  SendOutlined, 
  UploadOutlined, 
  FileOutlined,
  RobotOutlined
} from '@ant-design/icons'
import { UploadProps } from 'antd/es/upload'
import MessageBubble from './MessageBubble'
import { Message, FileInfo } from '../../types/store'
import { DialogueState } from '../../types/api'
import apiService from '../../services/api'
import './ChatContainer.css'

const { Content, Footer } = Layout
const { TextArea } = Input

export interface ChatContainerRef {
  triggerFileUpload: () => void
  triggerJsonUpload?: () => void
}

interface ChatContainerProps {
  messages: Message[]
  currentState: DialogueState
  isLoading: boolean
  currentFile: FileInfo | null
  onSendMessage: (content: string, fileId?: string) => void
  onFileUpload: (file: FileInfo) => void
  onError: (error: string) => void
  onActionClick?: (action: string) => void
  onDownloadReport?: (reportId: string) => void
}

const ChatContainer = forwardRef<ChatContainerRef, ChatContainerProps>(({
  messages,
  currentState,
  isLoading,
  currentFile,
  onSendMessage,
  onFileUpload,
  onError,
  onActionClick,
  onDownloadReport
}, ref) => {
  const [inputValue, setInputValue] = useState('')
  const [uploading, setUploading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const uploadButtonRef = useRef<HTMLDivElement>(null)
  const jsonUploadButtonRef = useRef<HTMLDivElement>(null)

  // Auto scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Expose methods to parent component
  useImperativeHandle(ref, () => ({
    triggerFileUpload: () => {
      // 触发上传按钮点击
      const uploadButton = uploadButtonRef.current?.querySelector('input[type="file"]') as HTMLInputElement
      if (uploadButton) {
        uploadButton.click()
      }
    },
    triggerJsonUpload: () => {
      // 触发JSON文件上传按钮点击
      const jsonUploadButton = jsonUploadButtonRef.current?.querySelector('input[type="file"]') as HTMLInputElement
      if (jsonUploadButton) {
        jsonUploadButton.click()
      }
    }
  }))

  const handleSendMessage = () => {
    if (!inputValue.trim()) return
    
    const content = inputValue.trim()
    setInputValue('')
    onSendMessage(content, currentFile?.file_id)
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const uploadProps: UploadProps = {
    name: 'file',
    accept: '.csv,.xlsx,.xls',
    showUploadList: false,
    beforeUpload: async (file) => {
      setUploading(true)
      try {
        const response = await apiService.uploadFile(file)
        // Convert FileUploadResponse to FileInfo
        const fileInfo: FileInfo = {
          file_id: response.file_id,
          filename: response.filename,
          file_size: response.size,
          upload_time: response.upload_time,
          available_channels: response.available_channels
        }
        onFileUpload(fileInfo)
        message.success(`文件 ${file.name} 上传成功`)
      } catch (error) {
        console.error('Upload error:', error)
        onError('文件上传失败，请重试')
        message.error('文件上传失败')
      } finally {
        setUploading(false)
      }
      return false // Prevent default upload
    },
  }

  const jsonUploadProps: UploadProps = {
    name: 'file',
    accept: '.json',
    showUploadList: false,
    beforeUpload: async (file) => {
      setUploading(true)
      try {
        // 读取JSON文件内容
        const text = await file.text()
        JSON.parse(text) // Validate JSON format
        
        // 这里应该验证JSON格式并使用配置生成报表
        // 暂时只显示成功消息
        message.success(`JSON配置文件 ${file.name} 加载成功`)
        
        // 可以在这里触发报表生成
        // await apiService.generateReport({ file_id: currentFile?.file_id, config: jsonConfig })
        
        onSendMessage(`已加载JSON配置文件：${file.name}`, currentFile?.file_id)
      } catch (error) {
        console.error('JSON upload error:', error)
        onError('JSON文件解析失败，请检查文件格式')
        message.error('JSON文件解析失败')
      } finally {
        setUploading(false)
      }
      return false // Prevent default upload
    },
  }

  const getPlaceholder = () => {
    switch (currentState) {
      case DialogueState.INITIAL:
        return '请上传数据文件或输入问题...'
      case DialogueState.FILE_UPLOADED:
        return '文件已上传，请告诉我您想生成什么类型的报表...'
      case DialogueState.CONFIGURING:
        return '请根据提示配置报表参数...'
      case DialogueState.GENERATING:
        return '正在生成报表，请稍候...'
      case DialogueState.COMPLETED:
        return '报表生成完成，您可以继续提问或上传新文件...'
      default:
        return '请输入您的问题...'
    }
  }

  const isInputDisabled = currentState === DialogueState.GENERATING || isLoading

  return (
    <Layout className="chat-container">
      <Content className="messages-area">
        <div className="messages-wrapper">
          {messages.length === 0 && (
            <div className="welcome-message">
              <RobotOutlined style={{ fontSize: 48, color: '#1890ff', marginBottom: 16 }} />
              <h3>欢迎使用DRIA AI报表生成系统</h3>
              <p>请上传您的数据文件，我将帮助您生成专业的分析报表</p>
            </div>
          )}
          
          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              isLoading={message.id === 'loading'}
              onActionClick={onActionClick}
              onDownloadReport={onDownloadReport}
            />
          ))}
          
          {isLoading && (
            <div className="message-item ai-message">
              <div className="message-avatar">
                <RobotOutlined />
              </div>
              <div className="message-content">
                <Spin size="small" />
                <span style={{ marginLeft: 8 }}>AI正在思考中...</span>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
      </Content>
      
      <Footer className="input-area">
        <div className="input-wrapper">
          {currentFile && (
            <div className="file-info">
              <FileOutlined style={{ color: '#1890ff' }} />
              <span>当前文件: {currentFile.filename}</span>
              <span className="file-size">
                ({currentFile.file_size > 1024 * 1024 
                  ? `${(currentFile.file_size / (1024 * 1024)).toFixed(2)} MB`
                  : `${(currentFile.file_size / 1024).toFixed(1)} KB`
                })
              </span>
            </div>
          )}
          
          <div className="input-controls">
            <Space.Compact style={{ width: '100%' }}>
              <TextArea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={getPlaceholder()}
                disabled={isInputDisabled}
                autoSize={{ minRows: 1, maxRows: 4 }}
                style={{ flex: 1 }}
              />
              <Space>
                <div ref={uploadButtonRef}>
                  <Upload {...uploadProps} disabled={uploading || isLoading}>
                    <Button 
                      icon={<UploadOutlined />} 
                      loading={uploading}
                      disabled={isLoading}
                    >
                      上传文件
                    </Button>
                  </Upload>
                </div>
                <div ref={jsonUploadButtonRef} style={{ display: 'none' }}>
                  <Upload {...jsonUploadProps} disabled={uploading || isLoading}>
                    <Button 
                      icon={<UploadOutlined />} 
                      loading={uploading}
                      disabled={isLoading}
                    >
                      上传JSON
                    </Button>
                  </Upload>
                </div>
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  onClick={handleSendMessage}
                  disabled={!inputValue.trim() || isInputDisabled}
                >
                  发送
                </Button>
              </Space>
            </Space.Compact>
          </div>
        </div>
      </Footer>
    </Layout>
  )
})

ChatContainer.displayName = 'ChatContainer'

export default ChatContainer
