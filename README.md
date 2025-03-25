# 双声道语音识别平台

这是一个基于HTTP的语音识别平台，专门用于处理音频，并提供高并发的API服务。该平台兼容macOS系统和M系列芯片。


## 功能特点

- 支持单声道音频的实时语音识别
- 支持双声道音频的语音识别
- 不区分单双声道，可直接整体识别，提高处理速度
- 提供五种识别模式：整体识别、简单识别、分轨识别、alignment片段识别和话者分离片段识别
- 详细的输出格式（包含说话内容和时间戳信息）
- 支持HTTP+JSON和HTTP+form-data两种接口形式
- 支持并发多用户调用

## 技术栈

- Python 3.8+
- Flask (Web框架)
- Whisper (OpenAI的语音识别模型)
- PyAudio/Librosa (音频处理)
- Gunicorn (WSGI HTTP服务器，用于生产环境)

## 安装与配置

### 环境要求

- macOS系统（兼容M系列芯片）
- Python 3.8+

### 安装步骤

1. 克隆仓库

```bash
git clone [仓库地址]
cd VoicePlatform-Tea-macmini-Stereo
```

2. 创建并激活虚拟环境

```bash
python -m venv venv
source venv/bin/activate
```

3. 安装依赖

```bash
pip install -r requirements.txt
```

4. 启动服务

```bash
python app.py
```

对于生产环境，建议使用Gunicorn：

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## API接口文档

### 1. 单声道实时语音识别接口（JSON）

- **URL**: `/api/v1/mono-asr`
- **方法**: POST
- **Content-Type**: application/json
- **请求体**:

```json
{
  "audio_data": "base64编码的音频数据",
  "audio_format": "wav"  // 可选参数，默认为wav
}
```

- **响应**:

```json
{
  "status": "success",
  "data": {
    "transcript": [
      {
        "text": "这是识别出的文本内容",
        "start_time": 0.0,
        "end_time": 2.5
      },
      {
        "text": "又一段识别内容",
        "start_time": 3.0,
        "end_time": 5.0
      }
    ]
  }
}
```

### 2. 单声道实时语音识别接口（form-data）

- **URL**: `/api/v1/mono-asr/upload`
- **方法**: POST
- **Content-Type**: multipart/form-data
- **表单字段**:
  - `audio_file`: 音频文件

- **响应**: 同上

### 3. 双声道语音识别接口（JSON）

- **URL**: `/api/v1/asr`
- **方法**: POST
- **Content-Type**: application/json
- **请求体**:

```json
{
  "audio_data": "base64编码的音频数据",
  "audio_format": "wav",
  "mode": "combined"  // 可选值: "combined"(整体识别)、"split"(分轨识别)、"alignment_segments"(分段精细识别)或"diarize_segments"(话者分离片段识别)
}
```

- **响应**:

```json
{
  "status": "success",
  "data": {
    "transcript": [
      {
        "speaker": "speakerA",
        "text": "你好，这是测试内容",
        "start_time": 0.0,
        "end_time": 2.5
      },
      {
        "speaker": "speakerB",
        "text": "好的，我明白了",
        "start_time": 3.0,
        "end_time": 5.0
      }
    ]
  }
}
```

### 4. 双声道语音识别接口（form-data）

- **URL**: `/api/v1/asr/upload`
- **方法**: POST
- **Content-Type**: multipart/form-data
- **表单字段**:
  - `audio_file`: 音频文件
  - `mode`: 识别模式（可选，默认为"combined"）

- **响应**: 同上

## 使用示例

### 使用curl发送单声道识别请求（JSON）

```bash
curl -X POST http://localhost:5000/api/v1/mono-asr \
  -H "Content-Type: application/json" \
  -d '{"audio_data":"<base64编码的音频数据>", "audio_format":"wav"}'
```

### 使用curl发送单声道识别请求（form-data）

```bash
curl -X POST http://localhost:5000/api/v1/mono-asr/upload \
  -F "audio_file=@/path/to/audio.wav"
```

### 使用curl发送双声道识别请求（JSON）

```bash
curl -X POST http://localhost:5000/api/v1/asr \
  -H "Content-Type: application/json" \
  -d '{"audio_data":"<base64编码的音频数据>", "audio_format":"wav", "mode":"split"}'
```

### 使用curl发送双声道识别请求（form-data）

```bash
curl -X POST http://localhost:5000/api/v1/asr/upload \
  -F "audio_file=@/path/to/audio.wav" \
  -F "mode=split"
```

## 识别模式说明

平台提供五种不同的识别模式，以满足不同的使用场景：

### 1. 单声道识别模式（mono-asr）

- 专为单声道音频设计的实时语音识别接口
- 直接使用ASR模型进行识别，不进行说话人分离处理
- 返回带有时间戳的文本段落
- 适用于实时语音识别场景，如语音助手、实时转写等

### 2. 整体识别模式（combined）

- 双声道识别的默认模式
- 不分辨双声道还是单声道，直接使用整体音频进行识别，不进行话者分离
- 返回带有时间戳的文本段落
- 适用于需要快速获取语音内容的场景

### 3. 分轨识别模式（split）

- 将双声道音频拆分为两个单声道，分别识别
- 自动将第一个声道标记为speakerA，第二个声道标记为speakerB
- 适用于已经物理分轨的录音，如会议录音、电话录音等

### 4. 分段精细识别模式（alignment_segments）

- 基于WhisperX的对齐结果（alignment_result.json）拆分原始音频
- 将每个片段单独进行ASR识别，并匹配说话人
- 生成更精准的识别结果
- 适用于需要高精度文字识别和时间戳的场景

### 5. 话者分离片段识别模式（diarize_segments）
- 使用pyannote/speaker-diarization-3.1模型进行说话人分离，生成diarize_segments.json文件
- 自动处理各种边缘情况，如无效的时间段、过短的片段等
- 对每个拆分的音频片段单独进行ASR识别
- 智能转换说话人标识为易读格式（SPEAKER_00 → speakerA，SPEAKER_01 → speakerB）
- 保留原始的说话人标识和时间戳信息
- 生成详细的识别摘要和结果文件，便于分析和调试
- 适用于需要复用已有的话者分离结果进行更精细识别的场景
- 也适用于需要高质量话者分离的新音频识别
- 提供完善的错误处理和回退机制，确保程序能够在各种情况下稳定运行

### 4. 配置系统

系统使用YAML格式的配置文件，默认为项目根目录下的`config.yaml`文件：

```bash
# 复制配置文件模板并修改
cp config.yaml.example config.yaml
# 根据需要编辑配置文件
nano config.yaml
```

您也可以创建`config.local.yaml`文件用于本地开发，该文件优先级高于`config.yaml`。

**配置文件结构：**

```yaml
# 环境配置
environment:
  # 模型文件路径
  model_dir: '/path/to/whisper/models/'
  hf_home: '/path/to/huggingface/home'

# API认证信息
auth:
  # Hugging Face API token - 用于访问pyannote/speaker-diarization模型
  hf_token: 'your_huggingface_token'

# ASR配置
asr:
  # 默认语言
  default_language: 'zh'
  # Whisper模型大小 ['tiny', 'base', 'small', 'medium', 'large']
  model_size: 'medium'
  # 批处理大小
  batch_size: 8
  # 固定说话人数量
  num_speakers: 2

# 临时文件管理
temp_files:
  # 是否在任务完成后自动清理临时文件
  auto_cleanup: false
  # 临时文件保留时间（小时）
  retention_hours: 24
  
# 服务器配置
server:
  # 最大上传内容大小（MB）
  max_content_length: 50
  # 服务器主机
  host: '0.0.0.0'
  # 服务器端口
  port: 5001
  # 是否开启调试模式
  debug: true
```

环境变量支持：您也可以通过环境变量`HF_TOKEN`设置Hugging Face API令牌。

### 5. 启动服务

```bash
python app.py
```

对于生产环境，建议使用Gunicorn：

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 许可证

[MIT License](LICENSE)