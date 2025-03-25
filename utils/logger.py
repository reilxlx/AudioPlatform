#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import json
from datetime import datetime

class Logger:
    """日志记录类，用于记录系统运行日志"""
    
    def __init__(self, log_dir=None):
        """初始化日志记录器
        
        Args:
            log_dir: 日志文件保存目录，如果为None则使用默认目录
        """
        # 设置日志目录
        if log_dir is None:
            # 在项目根目录下创建logs文件夹
            self.log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
        else:
            self.log_dir = log_dir
            
        # 确保日志目录存在
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 获取当前时间
        current_time = datetime.now()
        
        # 创建日志文件名，使用当前日期和小时
        log_file = os.path.join(self.log_dir, f'asr_{current_time.strftime("%Y-%m-%d_%H")}.log')
        
        # 配置日志记录器
        self.logger = logging.getLogger('asr_platform')
        self.logger.setLevel(logging.DEBUG)
        
        # 防止重复添加处理器
        if not self.logger.handlers:
            # 文件处理器
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            
            # 控制台处理器
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            
            # 设置日志格式
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            # 添加处理器
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
            
        # 记录当前小时，用于检查是否需要创建新的日志文件
        self.current_hour = current_time.hour
        self.last_check_time = current_time
    
    def _check_hour_change(self):
        """检查小时是否变更，如果变更则创建新的日志文件"""
        current_time = datetime.now()
        
        # 检查当前小时是否与记录的小时不同
        if current_time.hour != self.current_hour:
            # 更新当前小时
            self.current_hour = current_time.hour
            self.last_check_time = current_time
            
            # 创建新的日志文件
            log_file = os.path.join(self.log_dir, f'asr_{current_time.strftime("%Y-%m-%d_%H")}.log')
            
            # 移除旧的文件处理器
            for handler in self.logger.handlers[:]:  # 使用副本进行迭代
                if isinstance(handler, logging.FileHandler):
                    self.logger.removeHandler(handler)
                    handler.close()
            
            # 添加新的文件处理器
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def info(self, message):
        """记录信息级别日志"""
        self._check_hour_change()
        self.logger.info(message)
    
    def debug(self, message):
        """记录调试级别日志"""
        self._check_hour_change()
        self.logger.debug(message)
    
    def warning(self, message):
        """记录警告级别日志"""
        self._check_hour_change()
        self.logger.warning(message)
    
    def error(self, message):
        """记录错误级别日志"""
        self._check_hour_change()
        self.logger.error(message)
    
    def critical(self, message):
        """记录严重错误级别日志"""
        self._check_hour_change()
        self.logger.critical(message)
    
    def log_request(self, request_data, endpoint):
        """记录请求信息
        
        Args:
            request_data: 请求数据
            endpoint: API端点
        """
        try:
            if isinstance(request_data, dict):
                # 如果是JSON请求，记录JSON数据
                # 如果包含音频数据，不记录具体内容，只记录长度
                if 'audio_data' in request_data:
                    data_copy = request_data.copy()
                    data_copy['audio_data'] = f"[BASE64 AUDIO DATA, LENGTH: {len(request_data['audio_data'])}]"
                    log_data = data_copy
                else:
                    log_data = request_data
                
                self.info(f"请求 {endpoint}: {json.dumps(log_data, ensure_ascii=False)}")
            else:
                # 对于form-data请求，只记录文件名和请求参数
                self.info(f"请求 {endpoint}: [FORM DATA]")
        except Exception as e:
            self.error(f"记录请求信息失败: {str(e)}")
    
    def log_response(self, response_data, endpoint):
        """记录响应信息
        
        Args:
            response_data: 响应数据
            endpoint: API端点
        """
        try:
            self.info(f"响应 {endpoint}: {json.dumps(response_data, ensure_ascii=False)}")
        except Exception as e:
            self.error(f"记录响应信息失败: {str(e)}")
    
    def log_processing(self, message, data=None):
        """记录处理过程信息
        
        Args:
            message: 处理信息
            data: 相关数据
        """
        try:
            if data:
                self.info(f"{message}: {json.dumps(data, ensure_ascii=False)}")
            else:
                self.info(message)
        except Exception as e:
            self.error(f"记录处理信息失败: {str(e)}")