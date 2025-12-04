import { useState, useEffect, useRef, useCallback } from 'react'

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList
  resultIndex: number
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string
  message: string
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean
  interimResults: boolean
  lang: string
  start: () => void
  stop: () => void
  abort: () => void
  onresult: (event: SpeechRecognitionEvent) => void
  onerror: (event: SpeechRecognitionErrorEvent) => void
  onend: () => void
  onstart: () => void
}

interface UseSpeechRecognitionOptions {
  lang?: string
  continuous?: boolean
  interimResults?: boolean
  onResult?: (transcript: string, isFinal: boolean) => void
  onError?: (error: string) => void
}

interface UseSpeechRecognitionReturn {
  isSupported: boolean
  isListening: boolean
  transcript: string
  startListening: () => void
  stopListening: () => void
  error: string | null
}

// 获取 SpeechRecognition API
const getSpeechRecognition = (): SpeechRecognition | null => {
  if (typeof window === 'undefined') return null
  
  const SpeechRecognition = 
    (window as any).SpeechRecognition || 
    (window as any).webkitSpeechRecognition
  
  return SpeechRecognition ? new SpeechRecognition() : null
}

export const useSpeechRecognition = (
  options: UseSpeechRecognitionOptions = {}
): UseSpeechRecognitionReturn => {
  const {
    lang = 'zh-CN',
    continuous = false,
    interimResults = true,
    onResult,
    onError
  } = options

  const [isListening, setIsListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSupported, setIsSupported] = useState(false)
  
  const recognitionRef = useRef<SpeechRecognition | null>(null)
  const finalTranscriptRef = useRef('')
  const onResultRef = useRef<typeof onResult>()
  const onErrorRef = useRef<typeof onError>()

  // 始终保存最新的回调，避免因为依赖变化反复重建识别实例
  useEffect(() => {
    onResultRef.current = onResult
  }, [onResult])

  useEffect(() => {
    onErrorRef.current = onError
  }, [onError])

  // 初始化 SpeechRecognition
  useEffect(() => {
    const recognition = getSpeechRecognition()
    
    if (!recognition) {
      setIsSupported(false)
      return
    }

    setIsSupported(true)
    recognition.continuous = continuous
    recognition.interimResults = interimResults
    recognition.lang = lang

    // 处理识别结果
    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interimTranscript = ''
      let finalTranscript = ''

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript
        if (event.results[i].isFinal) {
          finalTranscript += transcript + ' '
        } else {
          interimTranscript += transcript
        }
      }

      if (finalTranscript) {
        finalTranscriptRef.current += finalTranscript
        setTranscript(finalTranscriptRef.current)
        onResultRef.current?.(finalTranscriptRef.current, true)
      } else if (interimTranscript) {
        const fullTranscript = finalTranscriptRef.current + interimTranscript
        setTranscript(fullTranscript)
        onResultRef.current?.(fullTranscript, false)
      }
    }

    // 处理错误
    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      const errorMessage = event.error === 'no-speech' 
        ? '未检测到语音，请重试'
        : event.error === 'audio-capture'
        ? '无法访问麦克风，请检查权限设置'
        : event.error === 'not-allowed'
        ? '麦克风权限被拒绝，请在浏览器设置中允许访问'
        : `语音识别错误: ${event.error}`
      
      setError(errorMessage)
      setIsListening(false)
      onErrorRef.current?.(errorMessage)
    }

    // 处理识别结束
    recognition.onend = () => {
      setIsListening(false)
    }

    // 处理识别开始
    recognition.onstart = () => {
      setIsListening(true)
      setError(null)
    }

    recognitionRef.current = recognition

    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop()
        } catch (e) {
          // 忽略停止时的错误
        }
      }
    }
  // 注意：不把 onResult / onError 放到依赖中，防止重复创建实例
  }, [lang, continuous, interimResults])

  const startListening = useCallback(() => {
    if (!recognitionRef.current) {
      setError('浏览器不支持语音识别')
      return
    }

    if (isListening) {
      return
    }

    try {
      finalTranscriptRef.current = ''
      setTranscript('')
      setError(null)
      recognitionRef.current.start()
    } catch (err: any) {
      const errorMessage = err.message || '启动语音识别失败'
      setError(errorMessage)
      onError?.(errorMessage)
    }
  }, [isListening, onError])

  const stopListening = useCallback(() => {
    if (!recognitionRef.current || !isListening) {
      return
    }

    try {
      recognitionRef.current.stop()
    } catch (err: any) {
      console.error('停止语音识别失败:', err)
    }
  }, [isListening])

  return {
    isSupported,
    isListening,
    transcript,
    startListening,
    stopListening,
    error
  }
}

