import React, { useState, useRef } from 'react'
import { Button, message } from 'antd'
import { UploadOutlined } from '@ant-design/icons'
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

  // 处理文件选择并直接上传
  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    if (!validateFile(file)) {
      // 清空文件输入
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
      return
    }

    // 直接上传文件，不需要确认步骤
    setIsUploading(true)

    try {
      const fileInfo = await apiService.uploadFile(file)

      message.success('文件上传成功！')
      onFileUploaded?.(fileInfo)
      
      // 重置状态
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
    }
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
          loading={isUploading}
        >
          {isUploading ? '上传中...' : '上传'}
        </Button>
      </div>
    </>
  )
}

export default FileUploadButton
