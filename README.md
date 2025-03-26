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
- 支持文本转语音（TTS）功能，使用ChatTTS模型

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

### 5. 文本转语音接口（TTS）

- **URL**: `/api/v1/tts`
- **方法**: POST
- **Content-Type**: application/json
- **请求体**:

```json
{
  "text": "要转换的文本内容",
  "temperature": 0.0003,  // 可选参数，控制生成的随机性
  "top_p": 0.7,          // 可选参数，top-p采样参数
  "top_k": 20,           // 可选参数，top-k采样参数
  "output_path": null    // 可选参数，指定输出文件路径，默认自动生成
}
```

- **响应**:

```json
{
  "status": "success",
  "data": {
    "audio_file_path": "/path/to/generated/audio.wav",  // 生成的音频文件路径
    "audio_data": "base64编码的音频数据",                // 音频文件的base64编码
    "sample_rate": 24000                                // 音频采样率
  }
}
```

### 6. Fish-Speech文本转语音接口

- **URL**: `/api/v1/fish-speech`
- **方法**: POST
- **Content-Type**: application/json
- **请求体**:

```json
{
  "model": "FishSpeech-1.5",        // 模型名称，当前支持"FishSpeech-1.5"
  "input": "要转换的文本内容",        // 必填，要转换的文本
  "voice": "/path/to/voice.wav",    // 可选，语音样本路径，用于克隆声音
  "response_format": "mp3"          // 可选，返回的音频格式，支持mp3,wav,ogg,flac，默认为"mp3"
}
```

- **响应**:

```json
{
  "status": "success",
  "data": {
    "audio_file_path": "/path/to/generated/audio.mp3",  // 生成的音频文件路径（服务器本地路径）
    "audio_data": "base64编码的音频数据",               // 音频文件的base64编码
    "format": "mp3",                                   // 音频格式
    "processing_time": "1.25秒"                         // 处理时间
  }
}
```

- **错误响应**:

```json
{
  "status": "error",
  "message": "错误信息"
}
```

可能的错误情况包括：
- 无效的请求数据
- 缺少文本数据 (input 字段)
- input 字段必须是非空字符串
- voice 字段必须是字符串
- response_format 字段必须是以下之一: mp3, wav, ogg, flac
- 语音样本文件不存在
- Fish-Speech API请求失败（连接问题、服务不可用等）

### 使用curl发送TTS请求

```bash
curl -X POST http://localhost:5000/api/v1/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "你好，这是一段测试文本",
    "temperature": 0.0003,
    "top_p": 0.7,
    "top_k": 20
  }'
```

### 使用curl发送Fish-Speech请求

```bash
curl -X POST http://localhost:5000/api/v1/fish-speech \
  -H "Content-Type: application/json" \
  -d '{
    "model": "FishSpeech-1.5",
    "input": "你好，这是一段使用FishSpeech-1.5模型生成的一段TTS语言，该语音特点为音色稳定，适合作为日常播放使用的音频。",
    "voice": "/path/to/voice_sample.wav",
    "response_format": "mp3"
  }' > response.json
```

然后你可以从响应中提取base64音频数据并保存为文件：

```bash
cat response.json | jq -r '.data.audio_data' | base64 --decode > output.mp3
```

或者直接使用响应中的本地文件路径进行试听。

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

平台提供四种不同的识别模式，以满足不同的使用场景：

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

### 4. 话者分离片段识别模式（diarize_segments）
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

## 项目结构

```
VoicePlatform-Tea-macmini-Stereo/
│
├── app.py                 # 主应用入口，提供HTTP API服务
├── config.yaml            # 配置文件
├── requirements.txt       # 项目依赖
│
├── src_asr/               # ASR相关代码目录
│   ├── __init__.py        # 包初始化文件
│   ├── asr_engine.py      # ASR引擎核心类
│   ├── asr_engine_segment.py  # ASR分段处理函数
│   ├── audio_processor.py     # 音频处理类
│   ├── audio_segment_extractor.py  # 音频分段提取器
│   └── speaker_segment_processor.py  # 说话人分段处理器
│
├── utils/                 # 通用工具类目录
│   ├── __init__.py        # 包初始化文件
│   ├── config_loader.py   # 配置加载器
│   ├── logger.py          # 日志类
│   └── temp_manager.py    # 临时文件管理器
│
├── logs/                  # 日志文件目录
└── temp_files/            # 临时文件目录
```

## 项目重构说明

为了提高代码的可维护性和模块化程度，我们对项目进行了如下重构：

1. **模块分离**：
   - 将ASR相关的代码移至`src_asr/`目录
   - 将通用工具类代码移至`utils/`目录

2. **导入路径更新**：
   - 所有模块的导入路径已经更新，使用包名进行导入
   - 例如：`from utils.logger import Logger`

3. **包初始化**：
   - 在`src_asr/`和`utils/`目录下添加了`__init__.py`文件
   - 定义了每个包导出的类和函数，方便其他模块导入

4. **路径处理优化**：
   - 修改了临时文件和日志文件的路径处理逻辑，确保在新的目录结构下能够正确找到相应目录

这样的重构有助于：
- 更清晰地区分不同功能模块
- 降低代码耦合度
- 方便后续功能扩展
- 提高代码的可读性和可维护性

## 版本更新说明

### 2023.03.30 更新

1. **修复Fish-Speech API二进制响应处理**:
   - 修复了Fish-Speech API响应处理逻辑，正确识别并处理二进制音频数据
   - 移除了错误的base64解码尝试，避免"string argument should contain only ASCII characters"错误
   - 优化了响应错误信息显示，限制错误文本长度，防止日志过长
   - 添加了二进制数据到base64的正确转换流程，确保API响应格式一致性

2. **错误处理增强**:
   - 改进了异常处理，加入了更多健全性检查
   - 优化了错误消息格式，提供更清晰的问题描述
   - 在错误信息中添加了更多上下文，便于排查问题

### 2023.03.29 更新

1. **优化中文显示**:
   - 修复了日志和API响应中的中文编码问题，使中文正确显示而不是Unicode转义序列
   - 改进了Flask JSON序列化配置，确保API响应中的中文字符直接可读
   - 优化了日志记录模块，提高了中文日志的可读性
   - 增强了文本预览功能，使日志中的中文文本内容更加友好

2. **日志系统增强**:
   - 改进了请求与响应的日志记录格式
   - 增加了更多有用的上下文信息到日志中
   - 优化了大型二进制数据的日志处理，提高日志文件的可读性和效率

### 2023.03.28 更新

1. **修复并优化Fish-Speech API**:
   - 修复了配置加载问题，解决了API URL为None导致的错误
   - 添加了新的`get_nested`方法，支持多级配置访问，如`tts.fish_speech.api_url`
   - 增强了错误处理和日志记录，包括详细的错误信息和堆栈跟踪
   - 添加了请求参数验证，防止无效请求导致服务器错误
   - 添加了处理时间统计，便于性能监控

2. **增强的响应格式**:
   - 在JSON响应中增加了处理时间信息
   - 添加了详细的错误响应格式，提供更清晰的错误信息
   - 改进了响应日志记录，不再记录完整的音频数据，只记录长度

3. **安全性增强**:
   - 添加了更严格的参数验证
   - 添加了文件存在性检查，避免访问不存在的文件
   - 添加了base64编码验证，确保返回的数据是有效的base64

### 2023.03.27 更新

1. **改进Fish-Speech API**:
   - 修改了Fish-Speech API的响应格式，现在返回JSON格式的响应，包含本地文件路径和base64编码的音频数据
   - 添加了自动将生成的音频保存到本地文件的功能，便于直接试听和测试
   - 更新了API文档和使用示例，展示如何从响应中提取数据

2. **新增Fish-Speech API支持**:
   - 添加了全新的`/api/v1/fish-speech`接口，支持使用FishSpeech-1.5模型进行文本转语音
   - 新接口支持语音克隆功能，可通过提供语音样本(`voice`参数)来模仿特定声音
   - 简化的响应格式，直接返回base64编码的音频数据

3. **配置增强**:
   - 在`config.yaml`中添加了`tts.fish_speech`配置节，支持自定义API URL和默认响应格式
   - 所有配置都可通过修改配置文件进行自定义，无需修改代码

4. **改进的文档**:
   - 更新了API文档，新增了Fish-Speech API的接口说明和使用示例
   - 添加了curl示例，展示如何调用新API并保存结果

## 工具脚本

### Base64转音频文件 (base64_to_audio.py)

这个脚本用于将base64编码的音频数据转换为音频文件并保存到本地。支持多种常见音频格式，如WAV、MP3、AAC、FLAC等。

#### 使用方法

**在Python代码中直接导入使用**:

```python
from base64_to_audio import base64_to_audio

# 使用默认设置（UUID自动生成文件名，wav格式）
output_path = base64_to_audio(base64_string)
print(f"音频文件已保存到: {output_path}")

# 指定输出文件路径
output_path = base64_to_audio(base64_string, output_file_path="output_audio.wav")

# 指定不同的音频格式
output_path = base64_to_audio(base64_string, format="mp3")

# 同时指定文件路径和格式
output_path = base64_to_audio(
    base64_string, 
    output_file_path="my_audio_file", 
    format="flac"
)
```

#### 功能特点

- 支持多种音频格式（WAV、MP3、AAC、FLAC等）
- 使用UUID自动生成唯一文件名（当未指定输出路径时）
- 自动创建输出目录（如果不存在）
- 自动添加文件扩展名（如果未指定）
- 处理带有MIME类型前缀的base64字符串（如"data:audio/wav;base64,..."）
- 提供清晰的错误提示
- 简单易用，无需复杂命令行参数