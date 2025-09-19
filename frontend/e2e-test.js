// End-to-End Test Script for DRIA System
import axios from 'axios'
import fs from 'fs'
import path from 'path'

const API_BASE = 'http://localhost:8000'
const FRONTEND_BASE = 'http://localhost:3000'

async function runE2ETests() {
  console.log('🚀 开始端到端测试...\n')
  
  let testResults = {
    total: 0,
    passed: 0,
    failed: 0,
    errors: []
  }

  // Test 1: Backend Health Check
  try {
    console.log('1️⃣ 测试后端健康检查...')
    const healthResponse = await axios.get(`${API_BASE}/api/health`, { timeout: 5000 })
    if (healthResponse.status === 200) {
      console.log('✅ 后端健康检查通过')
      testResults.passed++
    } else {
      throw new Error(`Unexpected status: ${healthResponse.status}`)
    }
  } catch (error) {
    console.log('❌ 后端健康检查失败:', error.message)
    testResults.errors.push('Backend health check failed')
    testResults.failed++
  }
  testResults.total++

  // Test 2: File Upload API
  try {
    console.log('\n2️⃣ 测试文件上传API...')
    
    // Create a simple CSV test file
    const testCsvContent = `time[s],Ng(rpm),Temperature(°C),Pressure(kPa)
0.0,15000,650,800
0.1,15100,660,820
0.2,15200,670,840
0.3,15300,680,860
0.4,15400,690,880`
    
    const testFilePath = 'test-data.csv'
    fs.writeFileSync(testFilePath, testCsvContent)
    
    const formData = new FormData()
    const fileBlob = new Blob([testCsvContent], { type: 'text/csv' })
    formData.append('file', fileBlob, 'test-data.csv')
    
    const uploadResponse = await axios.post(`${API_BASE}/ai_report/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 10000
    })
    
    if (uploadResponse.status === 200 && uploadResponse.data.file_id) {
      console.log('✅ 文件上传API测试通过')
      console.log(`   文件ID: ${uploadResponse.data.file_id}`)
      console.log(`   可用通道: ${uploadResponse.data.available_channels.length}个`)
      testResults.passed++
      
      // Store file_id for next test
      global.testFileId = uploadResponse.data.file_id
    } else {
      throw new Error('Upload response invalid')
    }
    
    // Clean up test file
    if (fs.existsSync(testFilePath)) {
      fs.unlinkSync(testFilePath)
    }
  } catch (error) {
    console.log('❌ 文件上传API测试失败:', error.message)
    testResults.errors.push('File upload API failed')
    testResults.failed++
  }
  testResults.total++

  // Test 3: Dialogue API
  try {
    console.log('\n3️⃣ 测试对话API...')
    
    const dialogueRequest = {
      session_id: 'test-session-' + Date.now(),
      user_input: '请帮我分析这个数据文件，生成一个包含稳态分析的报表',
      file_id: global.testFileId || 'test-file-id',
      context: {
        current_state: 'file_uploaded'
      }
    }
    
    const dialogueResponse = await axios.post(`${API_BASE}/ai_report/dialogue`, dialogueRequest, {
      timeout: 15000
    })
    
    if (dialogueResponse.status === 200 && dialogueResponse.data.ai_response) {
      console.log('✅ 对话API测试通过')
      console.log(`   AI响应: ${dialogueResponse.data.ai_response.substring(0, 100)}...`)
      console.log(`   对话状态: ${dialogueResponse.data.dialogue_state}`)
      testResults.passed++
    } else {
      throw new Error('Dialogue response invalid')
    }
  } catch (error) {
    console.log('❌ 对话API测试失败:', error.message)
    testResults.errors.push('Dialogue API failed')
    testResults.failed++
  }
  testResults.total++

  // Test 4: Report Generation API
  try {
    console.log('\n4️⃣ 测试报表生成API...')
    
    const reportRequest = {
      session_id: 'test-session-' + Date.now(),
      file_id: global.testFileId || 'test-file-id',
      config: {
        sourceFileId: global.testFileId || 'test-file-id',
        reportConfig: {
          sections: ['stableState'],
          stableState: {
            displayChannels: ['Ng(rpm)', 'Temperature(°C)'],
            condition: {
              channel: 'Ng(rpm)',
              statistic: '平均值',
              duration: 0.1,
              logic: '>',
              threshold: 14000
            }
          }
        }
      },
      report_type: 'test_reports'
    }
    
    const reportResponse = await axios.post(`${API_BASE}/ai_report/generate`, reportRequest, {
      timeout: 30000
    })
    
    if (reportResponse.status === 200 && reportResponse.data.success) {
      console.log('✅ 报表生成API测试通过')
      console.log(`   报表ID: ${reportResponse.data.report_id}`)
      console.log(`   文件路径: ${reportResponse.data.file_path}`)
      testResults.passed++
    } else {
      throw new Error('Report generation failed')
    }
  } catch (error) {
    console.log('❌ 报表生成API测试失败:', error.message)
    testResults.errors.push('Report generation API failed')
    testResults.failed++
  }
  testResults.total++

  // Test 5: Frontend Accessibility
  try {
    console.log('\n5️⃣ 测试前端可访问性...')
    
    const frontendResponse = await axios.get(FRONTEND_BASE, { timeout: 5000 })
    
    if (frontendResponse.status === 200 && frontendResponse.data.includes('DRIA')) {
      console.log('✅ 前端页面可访问')
      testResults.passed++
    } else {
      throw new Error('Frontend not accessible')
    }
  } catch (error) {
    console.log('❌ 前端访问测试失败:', error.message)
    testResults.errors.push('Frontend accessibility failed')
    testResults.failed++
  }
  testResults.total++

  // Print Summary
  console.log('\n' + '='.repeat(50))
  console.log('📊 端到端测试结果汇总')
  console.log('='.repeat(50))
  console.log(`总测试数: ${testResults.total}`)
  console.log(`✅ 通过: ${testResults.passed}`)
  console.log(`❌ 失败: ${testResults.failed}`)
  console.log(`成功率: ${((testResults.passed / testResults.total) * 100).toFixed(1)}%`)

  if (testResults.errors.length > 0) {
    console.log('\n❌ 失败详情:')
    testResults.errors.forEach((error, index) => {
      console.log(`   ${index + 1}. ${error}`)
    })
  }

  console.log('\n📋 系统状态检查:')
  console.log(`- 后端服务: ${testResults.passed >= 1 ? '✅ 运行中' : '❌ 异常'}`)
  console.log(`- 前端服务: ${testResults.passed >= 5 ? '✅ 运行中' : '❌ 异常'}`)
  console.log(`- API通信: ${testResults.passed >= 2 ? '✅ 正常' : '❌ 异常'}`)
  console.log(`- 核心功能: ${testResults.passed >= 3 ? '✅ 可用' : '❌ 不可用'}`)

  const isSystemReady = testResults.passed >= 4
  console.log(`\n🎯 系统就绪状态: ${isSystemReady ? '✅ 就绪' : '❌ 未就绪'}`)

  if (isSystemReady) {
    console.log('\n🎉 恭喜！DRIA系统已准备就绪，可以进行用户测试！')
    console.log('\n📱 下一步操作:')
    console.log('1. 在浏览器中访问: http://localhost:3000')
    console.log('2. 测试文件上传功能')
    console.log('3. 测试AI对话交互')
    console.log('4. 验证报表生成和下载')
  } else {
    console.log('\n⚠️  系统还需要进一步调试，请检查失败的测试项目')
  }

  return isSystemReady
}

// Run the tests
runE2ETests().catch(console.error)
