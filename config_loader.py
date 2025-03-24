#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import yaml
import logging
from pathlib import Path

class ConfigLoader:
    """配置加载器，用于读取配置文件"""
    
    def __init__(self, config_file=None):
        """初始化配置加载器
        
        Args:
            config_file: 配置文件路径，如果为None则使用默认路径
        """
        # 设置默认配置文件路径
        if config_file is None:
            # 首先查找当前目录下的config.local.yaml（本地开发配置）
            project_root = Path(__file__).parent.absolute()
            local_config = project_root / 'config.local.yaml'
            default_config = project_root / 'config.yaml'
            
            if local_config.exists():
                self.config_file = str(local_config)
                logging.info(f"使用本地配置文件: {self.config_file}")
            elif default_config.exists():
                self.config_file = str(default_config)
                logging.info(f"使用默认配置文件: {self.config_file}")
            else:
                raise FileNotFoundError("未找到配置文件，请确保存在config.yaml或config.local.yaml")
        else:
            self.config_file = config_file
        
        # 加载配置
        self.config = self._load_config()
    
    def _load_config(self):
        """加载配置文件
        
        Returns:
            dict: 配置字典
        """
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
            # 设置默认值
            if 'auth' not in config:
                config['auth'] = {}
            
            if 'hf_token' not in config['auth']:
                # 尝试从环境变量中读取
                config['auth']['hf_token'] = os.environ.get('HF_TOKEN', '')
                
            return config
        except Exception as e:
            logging.error(f"加载配置文件失败: {str(e)}")
            # 返回空配置以避免程序崩溃
            return {
                'environment': {'hf_home': '/tmp/hf_home'},
                'auth': {'hf_token': ''},
                'asr': {
                    'default_language': 'zh',
                    'model_size': 'medium',
                    'batch_size': 8,
                    'num_speakers': 2
                },
                'temp_files': {
                    'auto_cleanup': False,
                    'retention_hours': 24
                }
            }
    
    def get(self, section, key, default=None):
        """获取配置值
        
        Args:
            section: 配置节
            key: 配置键
            default: 默认值，如果配置不存在则返回此值
            
        Returns:
            配置值或默认值
        """
        if section in self.config and key in self.config[section]:
            return self.config[section][key]
        return default
    
    def get_hf_token(self):
        """获取HuggingFace API令牌
        
        Returns:
            str: HuggingFace API令牌
        """
        token = self.get('auth', 'hf_token', '')
        
        # 如果配置文件中未设置，尝试从环境变量获取
        if not token:
            token = os.environ.get('HF_TOKEN', '')
            
        return token
    
    def get_model_dir(self):
        """获取模型目录
        
        Returns:
            str: 模型目录路径
        """
        return self.get('environment', 'model_dir', './models')
    
    def get_hf_home(self):
        """获取HuggingFace主目录
        
        Returns:
            str: HuggingFace主目录路径
        """
        return self.get('environment', 'hf_home', '/tmp/hf_home')
    
    def get_default_language(self):
        """获取默认语言
        
        Returns:
            str: 默认语言代码
        """
        return self.get('asr', 'default_language', 'zh')
    
    def get_model_size(self):
        """获取Whisper模型大小
        
        Returns:
            str: 模型大小
        """
        return self.get('asr', 'model_size', 'medium')
    
    def get_batch_size(self):
        """获取批处理大小
        
        Returns:
            int: 批处理大小
        """
        return self.get('asr', 'batch_size', 8)
    
    def get_num_speakers(self):
        """获取固定说话人数量
        
        Returns:
            int: 说话人数量
        """
        return self.get('asr', 'num_speakers', 2) 