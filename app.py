#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
import json
import tempfile
import shutil
from werkzeug.utils import secure_filename
import time

# 导入自定义模块
from src_asr.audio_processor import AudioProcessor
from src_asr.asr_engine import ASREngine
from src_tts.tts_engine import TTSEngine
from utils.temp_manager import TempManager
from utils.logger import Logger
from utils.config_loader import ConfigLoader

# 加载配置
config = ConfigLoader()

# 导入Langfuse并初始化
from langfuse import Langfuse
langfuse = Langfuse(
    secret_key=config.get_langfuse_secret_key(),
    public_key=config.get_langfuse_public_key(),
    host=config.get_langfuse_host()
)

app = Flask(__name__)
CORS(app)  # 启用CORS支持

# 设置JSON配置，确保中文直接显示为UTF-8字符而不是Unicode转义序列
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# 配置
app.config['MAX_CONTENT_LENGTH'] = config.get_max_content_length() * 1024 * 1024  # 根据配置设置最大上传大小
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()  # 使用系统临时目录
os.environ['HF_HOME'] = config.get_hf_home()

# 初始化临时文件管理器
temp_manager = TempManager()

# 初始化日志记录器
logger = Logger()

# 初始化ASR引擎，传入logger对象
asr_engine = ASREngine(logger=logger)

# 初始化音频处理器
audio_processor = AudioProcessor(temp_manager=temp_manager, logger=logger)

# 初始化TTS引擎
tts_engine = TTSEngine(logger=logger)

# 确保json输出中文时不会被转义
def json_dumps_ensure_ascii_false(obj):
    return json.dumps(obj, ensure_ascii=False)

# 配置Flask应用json序列化方法 - 旧方法不适用于当前Flask版本
# app.json.dumps = json_dumps_ensure_ascii_false  # 这行会导致错误

# 使用兼容旧版本Flask的配置方式
from flask.json import JSONEncoder

class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        return super().default(obj)
        
    def encode(self, obj):
        return json.dumps(obj, ensure_ascii=False)

app.json_encoder = CustomJSONEncoder

@app.route('/api/v1/asr', methods=['POST'])
def asr_json():
    """处理JSON格式的ASR请求"""
    try:
        data = request.get_json()
        
        # 记录请求信息
        logger.log_request(data, '/api/v1/asr')
        
        if not data or 'audio_data' not in data:
            error_response = {
                'status': 'error',
                'message': '缺少音频数据'
            }
            logger.error(f"请求错误: 缺少音频数据")
            return jsonify(error_response), 400
        
        # 获取参数
        audio_data = data['audio_data']
        audio_format = data.get('audio_format', 'wav')
        mode = data.get('mode', 'combined')  # 默认为combined模式
        
        logger.info(f"请求参数: format={audio_format}, mode={mode}")
        
        # 解码base64音频数据
        try:
            audio_bytes = base64.b64decode(audio_data)
            logger.info(f"Base64解码成功，音频大小: {len(audio_bytes)} 字节")
        except Exception as e:
            error_response = {
                'status': 'error',
                'message': f'Base64解码失败: {str(e)}'
            }
            logger.error(f"Base64解码失败: {str(e)}")
            return jsonify(error_response), 400
        
        # 创建会话目录
        session_dir = temp_manager.create_session_dir()
        logger.info(f"创建会话目录: {session_dir}")
        
        # 保存原始音频到会话目录
        original_filename = f"original.{audio_format}"
        file_path = temp_manager.save_audio_file(audio_bytes, session_dir, original_filename)
        logger.info(f"保存原始音频到: {file_path}")
        
        # 处理音频并进行识别
        result = process_audio(file_path, mode, session_dir)
        
        # 检查处理结果是否包含错误
        if 'error' in result:
            error_response = {
                'status': 'error',
                'message': result['error']
            }
            logger.error(f"处理错误: {result['error']}")
            return jsonify(error_response), 400
        
        # 记录响应信息
        response_data = {
            'status': 'success',
            'data': result
        }
        logger.log_response(response_data, '/api/v1/asr')
        
        return jsonify(response_data)
        
    except Exception as e:
        error_response = {
            'status': 'error',
            'message': str(e)
        }
        logger.error(f"处理请求失败: {str(e)}")
        return jsonify(error_response), 500

@app.route('/api/v1/asr/upload', methods=['POST'])
def asr_upload():
    """处理表单上传的ASR请求"""
    try:
        # 记录请求信息
        logger.log_request({"form": request.form, "files": "包含音频文件"}, '/api/v1/asr/upload')
        
        if 'audio_file' not in request.files:
            error_response = {
                'status': 'error',
                'message': '缺少音频文件'
            }
            logger.error(f"请求错误: 缺少音频文件")
            return jsonify(error_response), 400
        
        audio_file = request.files['audio_file']
        if audio_file.filename == '':
            error_response = {
                'status': 'error',
                'message': '未选择文件'
            }
            logger.error(f"请求错误: 未选择文件")
            return jsonify(error_response), 400
        
        # 获取处理模式
        mode = request.form.get('mode', 'combined')  # 默认为combined模式
        
        logger.info(f"接收到文件: {audio_file.filename}, 处理模式: {mode}")
        
        # 创建会话目录
        session_dir = temp_manager.create_session_dir()
        logger.info(f"创建会话目录: {session_dir}")
        
        # 保存上传的文件
        filename = secure_filename(audio_file.filename)
        file_path = os.path.join(session_dir, filename)
        audio_file.save(file_path)
        logger.info(f"文件已保存到: {file_path}")
        
        # 处理音频并进行识别
        result = process_audio(file_path, mode, session_dir)
        
        # 检查处理结果是否包含错误
        if 'error' in result:
            error_response = {
                'status': 'error',
                'message': result['error']
            }
            logger.error(f"处理错误: {result['error']}")
            return jsonify(error_response), 400
        
        # 记录响应信息
        response_data = {
            'status': 'success',
            'data': result
        }
        logger.log_response(response_data, '/api/v1/asr/upload')
        
        return jsonify(response_data)
        
    except Exception as e:
        error_response = {
            'status': 'error',
            'message': str(e)
        }
        logger.error(f"处理请求失败: {str(e)}")
        return jsonify(error_response), 500

# 新增: 单声道实时语音识别接口 (JSON格式)
@app.route('/api/v1/mono-asr', methods=['POST'])
def mono_asr_json():
    """处理JSON格式的单声道实时语音识别请求"""
    try:
        data = request.get_json()
        
        # 记录请求信息
        logger.log_request(data, '/api/v1/mono-asr')
        
        if not data or 'audio_data' not in data:
            error_response = {
                'status': 'error',
                'message': '缺少音频数据'
            }
            logger.error(f"请求错误: 缺少音频数据")
            return jsonify(error_response), 400
        
        # 获取参数
        audio_data = data['audio_data']
        audio_format = data.get('audio_format', 'wav')
        
        logger.info(f"单声道识别请求: format={audio_format}")
        
        # 解码base64音频数据
        try:
            audio_bytes = base64.b64decode(audio_data)
            logger.info(f"Base64解码成功，音频大小: {len(audio_bytes)} 字节")
        except Exception as e:
            error_response = {
                'status': 'error',
                'message': f'Base64解码失败: {str(e)}'
            }
            logger.error(f"Base64解码失败: {str(e)}")
            return jsonify(error_response), 400
        
        # 创建会话目录
        session_dir = temp_manager.create_session_dir()
        logger.info(f"创建会话目录: {session_dir}")
        
        # 保存原始音频到会话目录
        original_filename = f"original-mono.{audio_format}"
        file_path = temp_manager.save_audio_file(audio_bytes, session_dir, original_filename)
        logger.info(f"保存原始音频到: {file_path}")
        
        # 直接调用ASR引擎进行识别，不进行说话人分离等处理
        logger.info("直接调用ASR引擎进行单声道识别")
        segments = asr_engine.recognize(file_path)
        
        # 生成总结文件
        summary_path = os.path.join(session_dir, "mono_asr_summary.txt")
        with open(summary_path, 'w', encoding='utf-8') as f:
            for segment in segments:
                f.write(f"{segment['start_time']:.1f}s - {segment['end_time']:.1f}s: {segment['text']}\n")
        logger.info(f"单声道识别摘要已保存至: {summary_path}")
        
        # 保存最终结果为易读的JSON格式
        final_results_path = os.path.join(session_dir, "mono_asr_results.json")
        with open(final_results_path, 'w', encoding='utf-8') as f:
            json.dump(segments, f, ensure_ascii=False, indent=2)
        logger.info(f"最终结果已保存至: {final_results_path}")
        
        # 记录响应信息
        response_data = {
            'status': 'success',
            'data': {
                'transcript': segments
            }
        }
        logger.log_response(response_data, '/api/v1/mono-asr')
        
        return jsonify(response_data)
        
    except Exception as e:
        error_response = {
            'status': 'error',
            'message': str(e)
        }
        logger.error(f"处理请求失败: {str(e)}")
        return jsonify(error_response), 500

# 新增: 单声道实时语音识别接口 (文件上传格式)
@app.route('/api/v1/mono-asr/upload', methods=['POST'])
def mono_asr_upload():
    """处理表单上传的单声道实时语音识别请求"""
    try:
        # 记录请求信息
        logger.log_request({"form": request.form, "files": "包含音频文件"}, '/api/v1/mono-asr/upload')
        
        if 'audio_file' not in request.files:
            error_response = {
                'status': 'error',
                'message': '缺少音频文件'
            }
            logger.error(f"请求错误: 缺少音频文件")
            return jsonify(error_response), 400
        
        audio_file = request.files['audio_file']
        if audio_file.filename == '':
            error_response = {
                'status': 'error',
                'message': '未选择文件'
            }
            logger.error(f"请求错误: 未选择文件")
            return jsonify(error_response), 400
        
        logger.info(f"接收到单声道音频文件: {audio_file.filename}")
        
        # 创建会话目录
        session_dir = temp_manager.create_session_dir()
        logger.info(f"创建会话目录: {session_dir}")
        
        # 保存上传的文件
        filename = secure_filename(audio_file.filename)
        file_path = os.path.join(session_dir, filename)
        audio_file.save(file_path)
        logger.info(f"文件已保存到: {file_path}")
        
        # 直接调用ASR引擎进行识别，不进行说话人分离等处理
        logger.info("直接调用ASR引擎进行单声道识别")
        segments = asr_engine.recognize(file_path)
        
        # 生成总结文件
        summary_path = os.path.join(session_dir, "mono_asr_summary.txt")
        with open(summary_path, 'w', encoding='utf-8') as f:
            for segment in segments:
                f.write(f"{segment['start_time']:.1f}s - {segment['end_time']:.1f}s: {segment['text']}\n")
        logger.info(f"单声道识别摘要已保存至: {summary_path}")
        
        # 保存最终结果为易读的JSON格式
        final_results_path = os.path.join(session_dir, "mono_asr_results.json")
        with open(final_results_path, 'w', encoding='utf-8') as f:
            json.dump(segments, f, ensure_ascii=False, indent=2)
        logger.info(f"最终结果已保存至: {final_results_path}")
        
        # 记录响应信息
        response_data = {
            'status': 'success',
            'data': {
                'transcript': segments
            }
        }
        logger.log_response(response_data, '/api/v1/mono-asr/upload')
        
        return jsonify(response_data)
        
    except Exception as e:
        error_response = {
            'status': 'error',
            'message': str(e)
        }
        logger.error(f"处理请求失败: {str(e)}")
        return jsonify(error_response), 500

def process_audio(file_path, mode, session_dir=None):
    """处理音频文件并返回识别结果
    
    Args:
        file_path: 音频文件路径
        mode: 处理模式，'split'表示分轨识别，'combined'表示整体识别
        session_dir: 会话目录，用于保存临时文件
        
    Returns:
        dict: 包含识别结果的字典
    """
    logger.info(f"开始处理音频: {file_path}, 模式: {mode}")
    
    # 如果没有提供会话目录，则创建新的会话目录
    if session_dir is None:
        session_dir = temp_manager.create_session_dir()
        logger.info(f"创建会话目录: {session_dir}")
    
    # 复制原始音频文件到会话目录
    filename = os.path.basename(file_path)
    dest_path = os.path.join(session_dir, filename)
    if file_path != dest_path:  # 避免复制到自身
        shutil.copy2(file_path, dest_path)
        logger.info(f"复制原始音频到会话目录: {dest_path}")
    
    # 检查模式是否有效
    valid_modes = ['split', 'combined', 'diarize_segments']
    if mode not in valid_modes:
        error_message = f"不支持的处理模式: {mode}，支持的模式有: {', '.join(valid_modes)}"
        logger.error(error_message)
        return {
            'error': error_message,
            'transcript': []
        }
    
    if mode == 'split':
        # 分轨识别模式
        logger.info("使用分轨识别模式")
        
        # 1. 分离双声道
        channel_files, session_dir = audio_processor.split_channels(dest_path, session_dir)
        logger.info(f"分离双声道完成，声道文件: {channel_files}")
        
        # 2. 对每个声道进行识别
        results = []
        for i, channel_file in enumerate(channel_files):
            speaker = f"speaker{'A' if i == 0 else 'B'}"
            logger.info(f"开始识别声道 {i} ({speaker}): {channel_file}")
            
            # 使用WhisperX模型进行识别，获取更精确的时间戳
            channel_result = asr_engine.recognize(channel_file)
            
            # 为每个结果添加说话人标识
            for segment in channel_result:
                segment['speaker'] = speaker
                results.append(segment)
            
            logger.info(f"声道 {i} ({speaker}) 识别完成，识别到 {len(channel_result)} 个片段")
            
            # 不再删除临时声道文件，因为已经保存到会话目录中
            # os.unlink(channel_file)
        
        # 3. 按时间戳排序
        results.sort(key=lambda x: x['start_time'])  
        logger.info(f"分轨识别完成，总共 {len(results)} 个片段")
        
    elif mode == 'diarize_segments':
        # 基于diarize_segments.json拆分并识别模式
        logger.info("使用diarize_segments.json拆分并识别模式")
        
        # 创建speaker_segments目录
        speaker_segments_dir = os.path.join(session_dir, "speaker_segments")
        os.makedirs(speaker_segments_dir, exist_ok=True)
        logger.info(f"创建speaker_segments目录: {speaker_segments_dir}")
        
        # 使用新开发的方法对音频进行处理，传递session_dir避免重复创建临时目录
        results = asr_engine.recognize_with_diarize_segments(dest_path, session_dir=session_dir)
        
        # 记录处理结果
        logger.info(f"diarize_segments识别完成，总共 {len(results)} 个片段")
        
        # 生成总结文件
        summary_path = os.path.join(session_dir, "diarize_segments_summary.txt")
        with open(summary_path, 'w', encoding='utf-8') as f:
            for segment in results:
                speaker = segment.get("speaker", "unknown")
                f.write(f"[{speaker}] {segment['start_time']:.1f}s - {segment['end_time']:.1f}s: {segment['text']}\n")
        logger.info(f"分段识别摘要已保存至: {summary_path}")
        
        # 保存最终结果为易读的JSON格式
        final_results_path = os.path.join(session_dir, "final_results.json")
        with open(final_results_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"最终结果已保存至: {final_results_path}")
        
    elif mode == 'combined':  # combined模式
        # 整体识别模式（不进行说话人分离）
        logger.info("使用整体识别模式（不进行说话人分离）")
        
        # 直接使用ASR引擎识别整个音频文件
        results = asr_engine.recognize(dest_path)
        
        # 记录处理结果
        logger.info(f"整体识别完成，总共 {len(results)} 个片段")
        
        # 生成识别摘要文本
        summary_path = os.path.join(session_dir, "combined_summary.txt")
        with open(summary_path, 'w', encoding='utf-8') as f:
            for segment in results:
                f.write(f"{segment['start_time']:.1f}s - {segment['end_time']:.1f}s: {segment['text']}\n")
        logger.info(f"识别摘要已保存至: {summary_path}")
        
        # 保存最终结果为易读的JSON格式
        final_results_path = os.path.join(session_dir, "final_results.json")
        with open(final_results_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"最终结果已保存至: {final_results_path}")
    
    # 记录处理结果
    logger.log_processing("音频处理结果", {"segments_count": len(results)})
    
    # 检查返回结果中是否包含错误信息
    if 'error' in results:
        return {
            'error': results['error'],
            'transcript': []
        }
    
    return {
        'transcript': results
    }

@app.route('/api/v1/tts', methods=['POST'])
def text_to_speech():
    """文本转语音接口"""
    try:
        data = request.get_json()
        
        # 记录请求信息
        logger.log_request(data, '/api/v1/tts')
        
        if not data or 'text' not in data:
            error_response = {
                'status': 'error',
                'message': '缺少文本数据'
            }
            logger.error(f"请求错误: 缺少文本数据")
            return jsonify(error_response), 400
        
        # 获取参数
        text = data['text']
        temperature = float(data.get('temperature', 0.0003))
        top_p = float(data.get('top_p', 0.7))
        top_k = int(data.get('top_k', 20))
        output_path = data.get('output_path', None)  # 可以指定输出路径，默认为None
        
        logger.info(f"TTS请求参数: temperature={temperature}, top_p={top_p}, top_k={top_k}")
        
        # 执行文本转语音
        try:
            # 生成文件名（如果未指定）
            if output_path is None:
                output_path = os.path.join("temp_files", f"tts_output_{int(time.time())}.wav")
            
            # 确保目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 保存到文件并返回base64
            audio_file_path, base64_audio = tts_engine.text_to_speech(
                text=text,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                output_path=output_path
            )
            
            # 记录响应信息
            response_data = {
                'status': 'success',
                'data': {
                    'audio_file_path': audio_file_path,
                    'audio_data': base64_audio,
                    'sample_rate': 24000  # ChatTTS的采样率
                }
            }
            logger.log_response(response_data, '/api/v1/tts')
            
            return jsonify(response_data)
            
        except Exception as e:
            error_response = {
                'status': 'error',
                'message': f'文本转语音失败: {str(e)}'
            }
            logger.error(f"文本转语音失败: {str(e)}")
            return jsonify(error_response), 500
            
    except Exception as e:
        error_response = {
            'status': 'error',
            'message': str(e)
        }
        logger.error(f"处理请求失败: {str(e)}")
        return jsonify(error_response), 500

@app.route('/api/v1/fish-speech', methods=['POST'])
def fish_speech():
    """使用Fish-Speech-1.5模型进行文本转语音"""
    # 创建Langfuse跟踪
    trace = langfuse.trace(
        name="fish-speech-api",
        metadata={"service": "fish-speech-tts"}
    )
    
    try:
        start_time = time.time()
        data = request.get_json()
        
        # 记录请求信息
        logger.log_request(data, '/api/v1/fish-speech')
        
        # 在Langfuse中记录请求信息
        trace_span = trace.span(
            name="fish-speech-request",
            input=data
        )
        
        if not data:
            error_response = {
                'status': 'error',
                'message': '无效的请求数据'
            }
            logger.error(f"请求错误: 无效的请求数据")
            
            # 记录失败到Langfuse
            trace_span.end(
                output=error_response,
                status_message="无效的请求数据",
                level="ERROR"
            )
            trace.update(status="failure", status_message="无效的请求数据")
            
            return jsonify(error_response), 400
        
        if 'input' not in data:
            error_response = {
                'status': 'error',
                'message': '缺少文本数据 (input 字段)'
            }
            logger.error(f"请求错误: 缺少文本数据 (input 字段)")
            
            # 记录失败到Langfuse
            trace_span.end(
                output=error_response,
                status_message="缺少文本数据",
                level="ERROR"
            )
            trace.update(status="failure", status_message="缺少文本数据")
            
            return jsonify(error_response), 400
        
        # 获取参数
        text = data['input']
        voice = data.get('voice', None)
        voice_txt = data.get('voice_txt', None)  # 新增 voice_txt 字段
        response_format = data.get('response_format', 'mp3')
        
        # 验证参数
        if not text or not isinstance(text, str):
            error_response = {
                'status': 'error',
                'message': 'input 字段必须是非空字符串'
            }
            logger.error(f"请求错误: input 字段必须是非空字符串")
            
            # 记录失败到Langfuse
            trace_span.end(
                output=error_response,
                status_message="input 字段必须是非空字符串",
                level="ERROR"
            )
            trace.update(status="failure", status_message="input 字段必须是非空字符串")
            
            return jsonify(error_response), 400
        
        if voice and not isinstance(voice, str):
            error_response = {
                'status': 'error',
                'message': 'voice 字段必须是字符串'
            }
            logger.error(f"请求错误: voice 字段必须是字符串")
            
            # 记录失败到Langfuse
            trace_span.end(
                output=error_response,
                status_message="voice 字段必须是字符串",
                level="ERROR"
            )
            trace.update(status="failure", status_message="voice 字段必须是字符串")
            
            return jsonify(error_response), 400
        
        if voice_txt and not isinstance(voice_txt, str):
            error_response = {
                'status': 'error',
                'message': 'voice_txt 字段必须是字符串'
            }
            logger.error(f"请求错误: voice_txt 字段必须是字符串")
            
            # 记录失败到Langfuse
            trace_span.end(
                output=error_response,
                status_message="voice_txt 字段必须是字符串",
                level="ERROR"
            )
            trace.update(status="failure", status_message="voice_txt 字段必须是字符串")
            
            return jsonify(error_response), 400
        
        if not isinstance(response_format, str) or response_format not in ['mp3', 'wav', 'ogg', 'flac']:
            error_response = {
                'status': 'error',
                'message': 'response_format 字段必须是以下之一: mp3, wav, ogg, flac'
            }
            logger.error(f"请求错误: 无效的 response_format: {response_format}")
            
            # 记录失败到Langfuse
            trace_span.end(
                output=error_response,
                status_message="无效的 response_format",
                level="ERROR"
            )
            trace.update(status="failure", status_message="无效的 response_format")
            
            return jsonify(error_response), 400
        
        # 直接显示请求文本的前50个字符，确保中文正确显示
        text_preview = text[:50] + "..." if len(text) > 50 else text
        voice_txt_preview = voice_txt[:50] + "..." if voice_txt and len(voice_txt) > 50 else voice_txt
        logger.info(f"Fish-Speech请求: text={text_preview}, voice={voice}, voice_txt={voice_txt_preview}, response_format={response_format}")
        
        # 结束请求跟踪span
        trace_span.end(
            output={
                "text_preview": text_preview, 
                "voice": voice, 
                "voice_txt_preview": voice_txt_preview, 
                "response_format": response_format
            },
            status_message="请求验证通过"
        )
        
        try:
            # 创建TTS处理span
            tts_span = trace.span(name="fish-speech-tts-processing")
            
            # 调用Fish-Speech引擎
            audio_file_path, audio_data_base64 = tts_engine.fish_speech(
                text=text,
                voice=voice,
                voice_txt=voice_txt,  # 传递 voice_txt 参数
                response_format=response_format
            )
            
            # 计算处理时间
            process_time = time.time() - start_time
            
            # 结束TTS处理span
            tts_span.end(
                output={
                    "audio_file_path": audio_file_path,
                    "format": response_format,
                    "audio_data": audio_data_base64,
                    "processing_time": f"{process_time:.2f}秒"
                },
                status_message="TTS处理成功"
            )
            
            # 返回JSON格式的响应
            response_data = {
                'status': 'success',
                'data': {
                    'audio_file_path': audio_file_path,
                    'audio_data': audio_data_base64,
                    'format': response_format,
                    'processing_time': f"{process_time:.2f}秒"
                }
            }
            
            # 记录响应信息，但不包含完整的audio_data
            log_response = {
                'status': 'success',
                'data': {
                    'audio_file_path': audio_file_path,
                    'format': response_format,
                    'audio_data_length': len(audio_data_base64),
                    'processing_time': f"{process_time:.2f}秒"
                }
            }
            logger.log_response(log_response, '/api/v1/fish-speech')
            
            logger.info(f"Fish-Speech转换成功: 处理时间={process_time:.2f}秒, 音频文件路径={audio_file_path}")
            
            # 完成整个跟踪
            trace.update(
                status="success",
                status_message=f"Fish-Speech转换成功，处理时间: {process_time:.2f}秒",
                metadata={
                    "processing_time_seconds": process_time,
                    "audio_format": response_format,
                    "text_length": len(text)
                }
            )
            
            return jsonify(response_data)
            
        except Exception as e:
            error_response = {
                'status': 'error',
                'message': f'Fish-Speech转换失败: {str(e)}'
            }
            logger.error(f"Fish-Speech转换失败: {str(e)}")
            # 记录堆栈跟踪
            import traceback
            logger.error(traceback.format_exc())
            
            # 如果存在TTS处理span，则结束它
            if 'tts_span' in locals():
                tts_span.end(
                    output=error_response,
                    status_message=f"Fish-Speech转换失败: {str(e)}",
                    level="ERROR"
                )
            
            # 更新跟踪状态
            trace.update(
                status="failure",
                status_message=f"Fish-Speech转换失败: {str(e)}",
                metadata={"error_details": traceback.format_exc()}
            )
            
            return jsonify(error_response), 500
        
    except Exception as e:
        error_response = {
            'status': 'error',
            'message': f'处理请求失败: {str(e)}'
        }
        logger.error(f"处理请求失败: {str(e)}")
        # 记录堆栈跟踪
        import traceback
        logger.error(traceback.format_exc())
        
        # 更新跟踪状态
        trace.update(
            status="failure",
            status_message=f"处理请求失败: {str(e)}",
            metadata={"error_details": traceback.format_exc()}
        )
        
        return jsonify(error_response), 500

@app.route('/api/v1/xinference-chat-tts', methods=['POST'])
def xinference_chat_tts():
    """使用xinference部署的ChatTTS模型进行文本转语音"""
    try:
        start_time = time.time()
        data = request.get_json()
        
        # 记录请求信息
        logger.log_request(data, '/api/v1/xinference-chat-tts')
        
        if not data:
            error_response = {
                'status': 'error',
                'message': '无效的请求数据'
            }
            logger.error(f"请求错误: 无效的请求数据")
            return jsonify(error_response), 400
        
        if 'input' not in data:
            error_response = {
                'status': 'error',
                'message': '缺少文本数据 (input 字段)'
            }
            logger.error(f"请求错误: 缺少文本数据 (input 字段)")
            return jsonify(error_response), 400
        
        # 获取参数
        text = data['input']
        voice = data.get('voice', '2155')  # 默认使用2155音色
        response_format = data.get('response_format', 'mp3')
        
        # 验证参数
        if not text or not isinstance(text, str):
            error_response = {
                'status': 'error',
                'message': 'input 字段必须是非空字符串'
            }
            logger.error(f"请求错误: input 字段必须是非空字符串")
            return jsonify(error_response), 400
        
        if voice and not isinstance(voice, (str, dict)):
            error_response = {
                'status': 'error',
                'message': 'voice 字段必须是字符串或字典'
            }
            logger.error(f"请求错误: voice 字段必须是字符串或字典")
            return jsonify(error_response), 400
        
        if not isinstance(response_format, str) or response_format not in ['mp3', 'wav', 'ogg', 'flac']:
            error_response = {
                'status': 'error',
                'message': 'response_format 字段必须是以下之一: mp3, wav, ogg, flac'
            }
            logger.error(f"请求错误: 无效的 response_format: {response_format}")
            return jsonify(error_response), 400
        
        # 直接显示请求文本的前50个字符，确保中文正确显示
        text_preview = text[:50] + "..." if len(text) > 50 else text
        voice_preview = voice if isinstance(voice, str) else "自定义音色数据"
        logger.info(f"Xinference ChatTTS请求: text={text_preview}, voice={voice_preview}, response_format={response_format}")
        
        try:
            # 调用Xinference ChatTTS引擎
            audio_file_path, audio_data_base64 = tts_engine.xinference_chat_tts(
                text=text,
                voice=voice,
                response_format=response_format
            )
            
            # 计算处理时间
            process_time = time.time() - start_time
            
            # 返回JSON格式的响应
            response_data = {
                'status': 'success',
                'data': {
                    'audio_file_path': audio_file_path,
                    'audio_data': audio_data_base64,
                    'format': response_format,
                    'processing_time': f"{process_time:.2f}秒"
                }
            }
            
            # 记录响应信息，但不包含完整的audio_data
            log_response = {
                'status': 'success',
                'data': {
                    'audio_file_path': audio_file_path,
                    'format': response_format,
                    'audio_data_length': len(audio_data_base64),
                    'processing_time': f"{process_time:.2f}秒"
                }
            }
            logger.log_response(log_response, '/api/v1/xinference-chat-tts')
            
            return jsonify(response_data)
            
        except Exception as e:
            error_response = {
                'status': 'error',
                'message': f'Xinference ChatTTS文本转语音失败: {str(e)}'
            }
            logger.error(f"Xinference ChatTTS文本转语音失败: {str(e)}")
            return jsonify(error_response), 500
            
    except Exception as e:
        error_response = {
            'status': 'error',
            'message': str(e)
        }
        logger.error(f"处理请求失败: {str(e)}")
        return jsonify(error_response), 500

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'ok',
        'message': 'Service is running'
    })

if __name__ == '__main__':
    app.run(host=config.get_host(), port=config.get_port(), debug=config.get_debug())