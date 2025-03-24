#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import tempfile
import random
from datetime import datetime

class TempManager:
    """临时文件管理类，用于管理音频处理过程中的临时文件"""
    
    def __init__(self, base_dir=None):
        """初始化临时文件管理器
        
        Args:
            base_dir: 临时文件基础目录，如果为None则使用默认目录
        """
        # 设置临时文件目录
        if base_dir is None:
            # 在项目根目录下创建temp_files文件夹
            self.base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_files')
        else:
            self.base_dir = base_dir
            
        # 确保临时文件目录存在
        os.makedirs(self.base_dir, exist_ok=True)
    
    def create_session_dir(self):
        """创建会话目录，用于存储单次请求的所有临时文件
        
        Returns:
            str: 会话目录路径
        """
        # 生成5位随机数
        random_number = random.randint(10000, 99999)
        
        # 使用日期_时间_5位随机数格式创建唯一的会话目录名
        session_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random_number}"
        session_dir = os.path.join(self.base_dir, session_id)
        
        # 创建会话目录
        os.makedirs(session_dir, exist_ok=True)
        
        return session_dir
    
    def save_audio_file(self, audio_data, session_dir, filename):
        """保存音频数据到会话目录
        
        Args:
            audio_data: 音频数据（字节）
            session_dir: 会话目录路径
            filename: 文件名
            
        Returns:
            str: 保存的文件路径
        """
        # 确保文件名有正确的扩展名
        if not filename.lower().endswith(('.wav', '.mp3', '.ogg', '.flac')):
            filename += '.wav'
        
        # 构建完整的文件路径
        file_path = os.path.join(session_dir, filename)
        
        # 保存音频数据
        with open(file_path, 'wb') as f:
            f.write(audio_data)
        
        return file_path
    
    def save_channel_file(self, channel_data, session_dir, channel_index, original_filename=None):
        """保存分离的声道文件到会话目录
        
        Args:
            channel_data: 声道数据路径（临时文件）
            session_dir: 会话目录路径
            channel_index: 声道索引（0或1）
            original_filename: 原始音频文件名，如果提供则使用原始文件名作为基础
            
        Returns:
            str: 保存的文件路径
        """
        # 构建声道文件名
        if original_filename:
            # 获取原始文件名（不含路径和扩展名）
            base_name = os.path.splitext(os.path.basename(original_filename))[0]
            channel_filename = f"{base_name}_{channel_index}.wav"
        else:
            channel_filename = f"channel_{channel_index}.wav"
        
        # 构建完整的文件路径
        file_path = os.path.join(session_dir, channel_filename)
        
        # 复制临时文件到会话目录
        shutil.copy2(channel_data, file_path)
        
        return file_path
    
    def create_temp_file(self, suffix='.wav'):
        """创建临时文件
        
        Args:
            suffix: 文件后缀
            
        Returns:
            str: 临时文件路径
        """
        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_file.close()
        
        return temp_file.name
    
    def cleanup_temp_files(self, file_paths):
        """清理临时文件
        
        Args:
            file_paths: 临时文件路径列表
        """
        for file_path in file_paths:
            if os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except Exception as e:
                    print(f"清理临时文件失败: {file_path}, 错误: {str(e)}")
    
    def cleanup_old_sessions(self, max_age_days=1):
        """清理旧的会话目录
        
        Args:
            max_age_days: 最大保留天数
        """
        # 获取当前时间
        now = datetime.now()
        
        # 遍历临时文件目录
        for session_id in os.listdir(self.base_dir):
            session_dir = os.path.join(self.base_dir, session_id)
            
            # 跳过非目录
            if not os.path.isdir(session_dir):
                continue
            
            try:
                # 尝试从目录名解析时间
                if '_' in session_id:
                    date_str = session_id.split('_')[0]
                    session_date = datetime.strptime(date_str, '%Y%m%d')
                    
                    # 计算会话目录的年龄（天）
                    age_days = (now - session_date).days
                    
                    # 如果会话目录超过最大保留天数，则删除
                    if age_days > max_age_days:
                        shutil.rmtree(session_dir, ignore_errors=True)
            except Exception as e:
                print(f"清理旧会话目录失败: {session_dir}, 错误: {str(e)}")