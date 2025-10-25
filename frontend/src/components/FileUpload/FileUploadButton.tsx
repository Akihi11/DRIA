import React, { useState, useRef } from 'react'
import { Button, message, Modal, Progress } from 'antd'
import { UploadOutlined, FileTextOutlined } from '@ant-design/icons'
import { FILE_CONSTRAINTS } from '../../utils/constants'
import apiService from '../../services/api'
import './FileUploadButton.css'

interface FileUploadButtonProps {
  onFileUploaded?: (fileInfo: any) => void
  onUploadError?: (error: string) => void
  disabled?: boolean
}

const FileUploadButton: React.FC<FileUploadButtonProps> = ({
  onFileUploaded,
  onUploadError,
  disabled = false
}) => {
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [showPreview, setShowPreview] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 验证文件类型
  const validateFile = (file: File): boolean => {
    const fileExtension = file.name.split('.').pop()?.toLowerCase()
    
    if (!fileExtension || !FILE_CONSTRAINTS.ALLOWED_TYPES.includes(fileExtension as 'csv' | 'xlsx' | 'xls')) {
      message.error(`只支持 ${FILE_CONSTRAINTS.ALLOWED_TYPES.join('、')} 格式的文件`)
      return false
    }

    if (file.size > FILE_CONSTRAINTS.MAX_SIZE) {
      message.error(`文件大小不能超过 ${Math.round(FILE_CONSTRAINTS.MAX_SIZE / 1024 / 1024)}MB`)
      return false
    }

    return true
  }

  // 处理文件选择
  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    if (!validateFile(file)) {
      // 清空文件输入
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
      return
    }

    setSelectedFile(file)
    setShowPreview(true)
  }

  // 上传文件
  const handleUpload = async () => {
    if (!selectedFile) return

    setIsUploading(true)
    setUploadProgress(0)

    try {
      // 模拟上传进度
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval)
            return prev
          }
          return prev + Math.random() * 10
        })
      }, 200)

      const fileInfo = await apiService.uploadFile(selectedFile)
      
      clearInterval(progressInterval)
      setUploadProgress(100)

      message.success('文件上传成功！')
      onFileUploaded?.(fileInfo)
      
      // 重置状态
      setSelectedFile(null)
      setShowPreview(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }

    } catch (error: any) {
      console.error('文件上传失败:', error)
      const errorMessage = error.response?.data?.detail || error.message || '文件上传失败'
      message.error(errorMessage)
      onUploadError?.(errorMessage)
    } finally {
      setIsUploading(false)
      setUploadProgress(0)
    }
  }

  // 取消上传
  const handleCancel = () => {
    setSelectedFile(null)
    setShowPreview(false)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  // 获取文件图标
  const getFileIcon = () => {
    return <FileTextOutlined style={{ fontSize: 24, color: '#1890ff' }} />
  }

  // 格式化文件大小
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  return (
    <>
      <div className="file-upload-container">
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
          disabled={disabled || isUploading}
        />
        
        <Button
          type="default"
          icon={<UploadOutlined />}
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled || isUploading}
          className="file-upload-button"
          title="上传CSV或Excel文件"
        >
          {isUploading ? '上传中...' : '上传'}
        </Button>
      </div>

      {/* 文件预览和上传确认模态框 */}
      <Modal
        title="确认上传文件"
        open={showPreview}
        onCancel={handleCancel}
        footer={[
          <Button key="cancel" onClick={handleCancel}>
            取消
          </Button>,
          <Button
            key="upload"
            type="primary"
            onClick={handleUpload}
            loading={isUploading}
          >
            {isUploading ? '上传中...' : '确认上传'}
          </Button>
        ]}
        width={500}
      >
        {selectedFile && (
          <div className="file-preview">
            <div className="file-info">
              <div className="file-icon">
                {getFileIcon()}
              </div>
              <div className="file-details">
                <div className="file-name">{selectedFile.name}</div>
                <div className="file-size">{formatFileSize(selectedFile.size)}</div>
                <div className="file-type">
                  文件类型: {selectedFile.name.split('.').pop()?.toUpperCase()}
                </div>
              </div>
            </div>
            
            {isUploading && (
              <div className="upload-progress">
                <Progress 
                  percent={Math.round(uploadProgress)} 
                  status={uploadProgress === 100 ? 'success' : 'active'}
                />
              </div>
            )}
          </div>
        )}
      </Modal>
    </>
  )
}

export default FileUploadButton
