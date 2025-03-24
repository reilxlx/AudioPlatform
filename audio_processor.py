#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import tempfile
import numpy as np
import librosa
import soundfile as sf
from pydub import AudioSegment
from temp_manager import TempManager
from logger import Logger
os.environ['HF_HOME'] = '/Users/reilx/Downloads/githubCode/voice'
class AudioProcessor:
    """音频处理类，用于处理双声道音频"""
    
    def __init__(self, temp_manager=None, logger=None):
        """初始化音频处理器
        
        Args:
            temp_manager: 临时文件管理器，如果为None则创建新的管理器
            logger: 日志记录器，如果为None则创建新的记录器
        """
        # 初始化临时文件管理器
        self.temp_manager = temp_manager if temp_manager else TempManager()
        
        # 初始化日志记录器
        self.logger = logger if logger else Logger(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs'))
        
        self.logger.info("音频处理器初始化完成")
    
    def split_channels(self, audio_path, session_dir=None):
        """将双声道音频分离为两个单声道音频文件
        
        Args:
            audio_path: 双声道音频文件路径
            session_dir: 会话目录，如果为None则创建新的会话目录
            
        Returns:
            list: 包含两个单声道音频文件路径的列表
            str: 会话目录路径
        """
        self.logger.info(f"开始分离双声道音频: {audio_path}")
        
        # 加载音频文件
        y, sr = librosa.load(audio_path, mono=False, sr=None)
        
        # 确保是双声道
        if y.ndim == 1:
            self.logger.error("提供的音频不是双声道")
            raise ValueError("提供的音频不是双声道")
        
        if y.shape[0] != 2:
            self.logger.error(f"预期双声道音频，但获得了{y.shape[0]}个声道")
            raise ValueError(f"预期双声道音频，但获得了{y.shape[0]}个声道")
        
        # 如果没有提供会话目录，则创建新的会话目录
        if session_dir is None:
            session_dir = self.temp_manager.create_session_dir()
            self.logger.info(f"创建会话目录: {session_dir}")
        
        # 分离声道
        channel_files = []
        for i in range(2):
            # 创建临时文件
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            temp_file.close()
            
            # 保存单声道音频到临时文件
            sf.write(temp_file.name, y[i], sr)
            
            # 将临时文件复制到会话目录，并传递原始音频文件名
            channel_path = self.temp_manager.save_channel_file(temp_file.name, session_dir, i, audio_path)
            channel_files.append(channel_path)
            
            self.logger.info(f"已保存声道 {i} 到: {channel_path}")
        
        return channel_files, session_dir
    
    def convert_to_wav(self, audio_path):
        """将音频转换为WAV格式
        
        Args:
            audio_path: 原始音频文件路径
            
        Returns:
            str: WAV格式音频文件路径
        """
        # 获取文件扩展名
        _, ext = os.path.splitext(audio_path)
        ext = ext.lower()[1:]  # 移除点号并转为小写
        
        # 如果已经是WAV格式，直接返回
        if ext == 'wav':
            return audio_path
        
        # 使用pydub转换格式
        audio = AudioSegment.from_file(audio_path, format=ext)
        
        # 创建临时WAV文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        temp_file.close()
        
        # 导出为WAV
        audio.export(temp_file.name, format='wav')
        
        return temp_file.name
    
    def normalize_audio(self, audio_path):
        """对音频进行归一化处理
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            str: 归一化后的音频文件路径
        """
        # 加载音频
        y, sr = librosa.load(audio_path, sr=None)
        
        # 归一化
        y_norm = librosa.util.normalize(y)
        
        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        temp_file.close()
        
        # 保存归一化后的音频
        sf.write(temp_file.name, y_norm, sr)
        
        return temp_file.name