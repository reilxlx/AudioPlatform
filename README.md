# AudioPlatform - 一站式语音处理平台

AudioPlatform定位提供语音识别(ASR)和文本转语音(TTS)功能，支持用户接口调用，可作为简单场景下的语音调度平台。

## 主要功能特点

### 语音识别功能 (ASR)
- **多种识别模式**：
  - 单声道识别 - 适用于常规语音识别场景
  - 双声道整体识别 - 直接处理整个音频文件，不区分声道
  - 双声道分轨识别 - 分别处理双声道音频的两个声道
  - 双声道话者分离识别 - 区分不同说话人并生成带标记的文本

- **详细输出信息**：
  - 识别文本内容
  - 时间戳
  - 说话人标识（适用于双声道音频）

### 文本转语音功能 (TTS)
- 支持多种TTS模型（chatts、fish-speech）
- 支持语音克隆功能（通过Fish-Speech模型）

### 系统特性
- 支持HTTP+JSON和HTTP+form-data两种接口形式
- 完善的日志记录系统
- 可配置的模型加载和处理参数

## 如何使用

### 语音识别 API

#### 单声道语音识别
```bash
# JSON格式请求
curl -X POST http://localhost:5001/api/v1/mono-asr \
  -H "Content-Type: application/json" \
  -d '{"audio_data":"<base64编码的音频数据>", "audio_format":"wav"}'

# 文件上传请求
curl -X POST http://localhost:5001/api/v1/mono-asr/upload \
  -F "audio_file=@/path/to/audio.wav"
```

#### 双声道语音识别
```bash
# JSON格式请求
curl -X POST http://localhost:5001/api/v1/asr \
  -H "Content-Type: application/json" \
  -d '{"audio_data":"<base64编码的音频数据>", "audio_format":"wav", "mode":"split"}'

# 文件上传请求
curl -X POST http://localhost:5001/api/v1/asr/upload \
  -F "audio_file=@/path/to/audio.wav" \
  -F "mode=split"
```

识别模式选项：
- `combined` - 整体识别（默认）
- `split` - 分轨识别
- `diarize_segments` - 话者分离片段识别

### 文本转语音 API

```bash
# 标准TTS请求
curl -X POST http://localhost:5001/api/v1/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "要转换的文本内容",
    "temperature": 0.0003,
    "top_p": 0.7,
    "top_k": 20
  }'

# Fish-Speech TTS请求（支持语音克隆）
curl -X POST http://localhost:5001/api/v1/fish-speech \
  -H "Content-Type: application/json" \
  -d '{
    "model": "FishSpeech-1.5",
    "input": "要转换的文本内容",
    "voice": "/path/to/voice_sample.wav",
    "response_format": "mp3"
  }'
```

### 启动服务

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 配置系统（可选）：
```bash
cp config.yaml.example config.yaml
# 编辑 config.yaml 文件配置相关参数
```

3. 启动服务：
```bash
python app.py
```

或在生产环境使用Gunicorn：
```bash
gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

