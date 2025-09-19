import React, { useState, useEffect, useRef } from 'react'
import { message } from 'antd'
import ChatContainer, { ChatContainerRef } from '../components/Chat/ChatContainer'
import { Message, FileInfo } from '../types/store'
import { DialogueState } from '../types/api'
import apiService from '../services/api'
import aiService from '../services/aiService'
import { v4 as uuidv4 } from 'uuid'

const ChatPage: React.FC = () => {
  const [sessionId, setSessionId] = useState<string>('')
  const [messages, setMessages] = useState<Message[]>([])
  const [currentState, setCurrentState] = useState<DialogueState>(DialogueState.INITIAL)
  const [isLoading, setIsLoading] = useState(false)
  const [currentFile, setCurrentFile] = useState<FileInfo | null>(null)
  const [, setError] = useState<string | null>(null)
  const chatContainerRef = useRef<ChatContainerRef>(null)
  
  // 配置状态跟踪
  const [configContext, setConfigContext] = useState({
    stableStateConfigured: false,
    functionalConfigured: false,
    statusEvalConfigured: false,
    stableChannel: '',
    reportType: '' // 'stable', 'functional', 'status', 'complete', 'custom'
  })

  // Initialize session on component mount
  useEffect(() => {
    const newSessionId = uuidv4()
    setSessionId(newSessionId)
    
    // Add welcome message
    const welcomeMessage: Message = {
      id: uuidv4(),
      type: 'ai',
      content: '您好！我是DRIA AI报表生成助手。请上传您的数据文件，我将帮助您生成专业的分析报表。',
      timestamp: new Date(),
      metadata: {
        suggestedActions: ['上传CSV文件', '上传Excel文件']
      }
    }
    
    setMessages([welcomeMessage])
  }, [])

  const handleSendMessage = async (content: string, _fileId?: string) => {
    if (!sessionId) return

    // Add user message
    const userMessage: Message = {
      id: uuidv4(),
      type: 'user',
      content,
      timestamp: new Date()
    }
    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)
    setError(null)

    try {
      // 更新配置上下文
      const input = content.toLowerCase()
      let updatedContext = { ...configContext }
      
      // 检测报表类型选择
      if (input.includes('稳态')) updatedContext.reportType = 'stable'
      if (input.includes('功能')) updatedContext.reportType = 'functional'
      if (input.includes('状态') || input.includes('评估')) updatedContext.reportType = 'status'
      if (input.includes('完整') || input.includes('全部')) updatedContext.reportType = 'complete'
      if (input.includes('其他') || input.includes('json')) updatedContext.reportType = 'custom'
      
      // 检测配置完成
      if (input.includes('使用 ng') || input.includes('使用ng')) {
        updatedContext.stableChannel = 'Ng(rpm)'
        updatedContext.stableStateConfigured = true
      }
      if (input.includes('全部指标') || (input.includes('确认') && updatedContext.reportType === 'functional')) {
        updatedContext.functionalConfigured = true
      }
      if (input.includes('全部项目') || (input.includes('确认') && updatedContext.reportType === 'status')) {
        updatedContext.statusEvalConfigured = true
      }
      
      setConfigContext(updatedContext)
      
      // 使用AI服务处理对话
      const aiResponse = await aiService.processDialogue(content, currentFile, {
        currentState,
        sessionId,
        ...updatedContext
      })

      // Add AI response
      const aiMessage: Message = {
        id: uuidv4(),
        type: 'ai',
        content: aiResponse.content,
        timestamp: new Date(),
        metadata: {
          suggestedActions: aiResponse.suggestedActions
        }
      }

      setMessages(prev => [...prev, aiMessage])

      // 更新对话状态
      if (aiResponse.isComplete) {
        setCurrentState(DialogueState.COMPLETED)
        
        // 添加报表下载消息（带气泡）
        const downloadMessage: Message = {
          id: uuidv4(),
          type: 'ai',
          content: '✅ 报表生成成功！您可以点击下方按钮下载报表文件。',
          timestamp: new Date(),
          metadata: {
            reportId: 'mock-report-' + Date.now(), // 模拟报表ID
            suggestedActions: ['下载报表', '查看报表列表', '生成新报表']
          }
        }
        setTimeout(() => {
          setMessages(prev => [...prev, downloadMessage])
          message.success('报表生成完成！')
        }, 1500)
        
      } else if (currentFile) {
        setCurrentState(DialogueState.CONFIGURING)
      } else {
        setCurrentState(DialogueState.INITIAL)
      }

    } catch (error) {
      console.error('Dialogue error:', error)
      const errorMessage = '抱歉，处理您的请求时出现了错误。请稍后重试。'
      setError(errorMessage)
      
      const aiErrorMessage: Message = {
        id: uuidv4(),
        type: 'ai',
        content: errorMessage,
        timestamp: new Date()
      }
      setMessages(prev => [...prev, aiErrorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleFileUpload = async (file: FileInfo) => {
    setCurrentFile(file)
    setCurrentState(DialogueState.FILE_UPLOADED)
    
    // Add system message about file upload immediately
    const fileMessage: Message = {
      id: uuidv4(),
      type: 'system',
      content: `文件 "${file.filename}" 上传成功！检测到 ${file.available_channels?.length || 0} 个数据通道。`,
      timestamp: new Date(),
      metadata: {
        fileInfo: file,
        channelStats: null // Will be loaded asynchronously
      }
    }
    setMessages(prev => [...prev, fileMessage])

    // 不再自动发送消息，而是添加一个AI提示消息
    setTimeout(() => {
      const aiPromptMessage: Message = {
        id: uuidv4(),
        type: 'ai',
        content: '文件已成功上传！请告诉我您想生成什么类型的报表：',
        timestamp: new Date(),
        metadata: {
          suggestedActions: ['生成稳态报表', '生成功能指标报表', '生成状态评估报表', '生成完整报表', '上传JSON配置文件']
        }
      }
      setMessages(prev => [...prev, aiPromptMessage])
    }, 500)
    
    // Load channel statistics in background (non-blocking)
    apiService.getFileChannels(file.file_id)
      .then(stats => {
        console.log('[DEBUG] 获取到的统计信息:', stats)
        // Update the message metadata with channel stats
        setMessages(prev => prev.map(msg => 
          msg.id === fileMessage.id 
            ? { ...msg, metadata: { ...msg.metadata, channelStats: stats.channels } }
            : msg
        ))
      })
      .catch(error => {
        console.error('[ERROR] Failed to get channel stats:', error)
      })
  }

  const handleError = (errorMessage: string) => {
    setError(errorMessage)
    message.error(errorMessage)
  }

  const handleDownloadReport = async (reportId: string) => {
    try {
      const blob = await apiService.downloadReport(reportId)
      
      // Create download link
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `report_${reportId}.xlsx`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
      
      message.success('报表下载成功')
    } catch (error) {
      console.error('Download error:', error)
      message.error('报表下载失败')
    }
  }

  const handleActionClick = (action: string) => {
    // 判断是否是上传文件的操作
    if (action.includes('上传') && (action.includes('CSV') || action.includes('Excel'))) {
      // 直接触发文件上传对话框
      chatContainerRef.current?.triggerFileUpload()
      return
    }
    
    // 判断是否是上传JSON配置文件
    if (action.includes('上传JSON配置文件')) {
      // 触发JSON文件上传
      chatContainerRef.current?.triggerJsonUpload?.()
      return
    }
    
    // 判断是否是下载报表操作
    if (action.includes('下载报表')) {
      // 从最后一条包含reportId的消息中获取reportId
      const reportMessage = [...messages].reverse().find(m => m.metadata?.reportId)
      if (reportMessage?.metadata?.reportId) {
        handleDownloadReport(reportMessage.metadata.reportId)
      }
      return
    }
    
    
    // 其他建议按钮，正常发送消息
    handleSendMessage(action, currentFile?.file_id)
  }

  return (
    <div style={{ height: '100%' }}>
      <ChatContainer
        ref={chatContainerRef}
        messages={messages}
        currentState={currentState}
        isLoading={isLoading}
        currentFile={currentFile}
        onSendMessage={handleSendMessage}
        onFileUpload={handleFileUpload}
        onError={handleError}
        onActionClick={handleActionClick}
        onDownloadReport={handleDownloadReport}
      />
    </div>
  )
}

export default ChatPage
