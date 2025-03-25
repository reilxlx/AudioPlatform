#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import tempfile
import numpy as np
import librosa
import soundfile as sf
from utils.temp_manager import TempManager

class AudioSegmentExtractor:
    """音频片段提取器，用于从音频文件中提取指定时间段的片段"""
    
    def __init__(self, temp_manager=None):
        """初始化音频片段提取器
        
        Args:
            temp_manager: 临时文件管理器，如果为None则创建新的管理器
        """
        # 初始化临时文件管理器
        self.temp_manager = temp_manager if temp_manager else TempManager()
    
    def extract_segment(self, audio_path, start_time, end_time, session_dir=None, speaker_id=None):
        """从音频文件中提取指定时间段的片段
        
        Args:
            audio_path: 音频文件路径
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            session_dir: 会话目录，如果为None则使用临时目录
            speaker_id: 说话人ID，用于生成文件名
            
        Returns:
            str: 提取的音频片段文件路径
        """
        # 加载音频文件
        y, sr = librosa.load(audio_path, sr=None)
        
        # 计算开始和结束的采样点
        start_sample = int(start_time * sr)
        end_sample = int(end_time * sr)
        
        # 确保索引在有效范围内
        if start_sample >= len(y):
            start_sample = len(y) - 1
        if end_sample >= len(y):
            end_sample = len(y) - 1
        
        # 提取音频片段
        if end_sample > start_sample:
            segment_audio = y[start_sample:end_sample]
        else:
            # 处理边界情况
            segment_audio = np.zeros(1 * sr)  # 1秒静音
        
        # 如果没有提供会话目录，则创建临时文件
        if session_dir is None:
            # 创建临时文件
            temp_file = self.temp_manager.create_temp_file(suffix='.wav')
            # 保存音频片段
            sf.write(temp_file, segment_audio, sr)
            return temp_file
        else:
            # 构建文件名
            if speaker_id:
                filename = f"{os.path.basename(audio_path).split('.')[0]}_{speaker_id}_{start_time:.2f}_{end_time:.2f}.wav"
            else:
                filename = f"{os.path.basename(audio_path).split('.')[0]}_{start_time:.2f}_{end_time:.2f}.wav"
            
            # 构建完整的文件路径
            file_path = os.path.join(session_dir, filename)
            
            # 保存音频片段
            sf.write(file_path, segment_audio, sr)
            
            return file_path
    
    def extract_segments_from_diarization(self, audio_path, diarize_segments, session_dir):
        """根据说话人分离结果提取音频片段
        
        Args:
            audio_path: 音频文件路径
            diarize_segments: 说话人分离结果，格式为{"segments": [{"speaker": "SPEAKER_XX", "start": float, "end": float}, ...]}
            session_dir: 会话目录
            
        Returns:
            dict: 包含每个片段信息和对应音频文件路径的字典
        """
        # 确保会话目录存在
        os.makedirs(session_dir, exist_ok=True)
        
        # 使用指定的session_dir作为直接保存目录，不再创建额外的segments子目录
        # 在调用此方法时，session_dir应该已经是speaker_segments目录
        
        # 提取每个片段
        segment_files = []
        for i, segment in enumerate(diarize_segments["segments"]):
            speaker = segment["speaker"]
            start_time = segment["start"]
            end_time = segment["end"]
            
            # 提取音频片段
            segment_path = self.extract_segment(
                audio_path, 
                start_time, 
                end_time, 
                session_dir, 
                speaker
            )
            
            # 添加到结果列表
            segment_files.append({
                "index": i,
                "speaker": speaker,
                "start_time": start_time,
                "end_time": end_time,
                "audio_path": segment_path
            })
        
        return segment_files