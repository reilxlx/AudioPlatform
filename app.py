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

# 导入自定义模块
from audio_processor import AudioProcessor
from asr_engine import ASREngine
from temp_manager import TempManager
from logger import Logger
from config_loader import ConfigLoader

# 加载配置
config = ConfigLoader()

app = Flask(__name__)
CORS(app)  # 启用CORS支持

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

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'ok',
        'message': 'Service is running'
    })

if __name__ == '__main__':
    app.run(host=config.get_host(), port=config.get_port(), debug=config.get_debug())