/**
 * 前端功能测试脚本
 * 用于验证文件上传和对话功能
 */

console.log('🧪 开始前端功能测试...')

// 测试文件上传
async function testFileUpload() {
  console.log('📁 测试文件上传功能...')
  
  try {
    // 创建一个测试文件
    const testData = 'time,Ng(rpm),Temperature(°C),Pressure(kPa)\n0,1000,25,101\n1,2000,30,102\n2,3000,35,103'
    const blob = new Blob([testData], { type: 'text/csv' })
    const file = new File([blob], 'test_data.csv', { type: 'text/csv' })
    
    const formData = new FormData()
    formData.append('file', file)
    
    const response = await fetch('/api/upload', {
      method: 'POST',
      body: formData
    })
    
    if (response.ok) {
      const result = await response.json()
      console.log('✅ 文件上传成功:', result)
      return result
    } else {
      console.error('❌ 文件上传失败:', response.status, response.statusText)
      return null
    }
  } catch (error) {
    console.error('❌ 文件上传错误:', error)
    return null
  }
}

// 测试健康检查
async function testHealthCheck() {
  console.log('🏥 测试健康检查...')
  
  try {
    const response = await fetch('/api/health')
    if (response.ok) {
      const result = await response.json()
      console.log('✅ 健康检查成功:', result)
      return true
    } else {
      console.error('❌ 健康检查失败:', response.status)
      return false
    }
  } catch (error) {
    console.error('❌ 健康检查错误:', error)
    return false
  }
}

// 运行所有测试
async function runAllTests() {
  console.log('🚀 开始运行所有测试...')
  
  // 1. 健康检查
  const healthOk = await testHealthCheck()
  if (!healthOk) {
    console.error('❌ 后端服务不可用，停止测试')
    return
  }
  
  // 2. 文件上传
  const uploadResult = await testFileUpload()
  if (uploadResult) {
    console.log('✅ 所有测试通过！')
    console.log('📊 测试结果:', {
      healthCheck: '✅ 通过',
      fileUpload: '✅ 通过',
      fileId: uploadResult.file_id,
      channels: uploadResult.channels
    })
  } else {
    console.error('❌ 部分测试失败')
  }
}

// 自动运行测试
runAllTests()

// 导出测试函数供手动调用
window.testFileUpload = testFileUpload
window.testHealthCheck = testHealthCheck
window.runAllTests = runAllTests

console.log('💡 提示: 在浏览器控制台中运行以下命令进行测试:')
console.log('  - testHealthCheck()  // 测试健康检查')
console.log('  - testFileUpload()   // 测试文件上传')
console.log('  - runAllTests()      // 运行所有测试')
