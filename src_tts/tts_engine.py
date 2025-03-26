#!/usr/bin/env python
# -*- coding: utf-8 -*-

import torch
import torchaudio
import base64
import numpy as np
import lzma
import pybase16384 as b14
from utils.logger import Logger
import time
import requests
import json
from utils.config_loader import ConfigLoader

def tensor_to_str(spk_emb):
    """将音色张量转换为压缩编码的字符串
    
    Args:
        spk_emb (torch.Tensor): 音色嵌入张量
        
    Returns:
        str: 编码后的字符串
    """
    # 将Tensor转换为NumPy数组
    spk_emb_np = spk_emb.cpu().numpy().astype(np.float16)
    # 将NumPy数组编码为字符串
    spk_emb_str = b14.encode_to_string(lzma.compress(spk_emb_np, format=lzma.FORMAT_RAW, filters=[
        {"id": lzma.FILTER_LZMA2, "preset": 9 | lzma.PRESET_EXTREME}]))
    return spk_emb_str

class TTSEngine:
    def __init__(self, logger=None):
        """初始化TTS引擎"""
        self.logger = logger or Logger()
        self.chat = None
        self.spk_emb_str = None
        self.config = ConfigLoader()
        self._initialize_model()
        
    def _initialize_model(self):
        """初始化ChatTTS模型"""
        try:
            # 配置torch设置
            torch._dynamo.config.cache_size_limit = 64
            torch._dynamo.config.suppress_errors = True
            torch.set_float32_matmul_precision('high')
            
            # 导入并初始化ChatTTS
            import ChatTTS
            self.chat = ChatTTS.Chat()
            self.chat.load(compile=False)
            
            # 加载音色文件并编码
            spk = torch.load("seed_id/seed_2155_restored_emb-woman.pt", map_location=torch.device('cpu')).detach()
            self.spk_emb_str = tensor_to_str(spk)
            
            self.logger.info("TTS模型初始化成功")
        except Exception as e:
            self.logger.error(f"TTS模型初始化失败: {str(e)}")
            raise
    
    def text_to_speech(self, text, temperature=0.0003, top_p=0.7, top_k=20, output_path=None):
        """将文本转换为语音并保存为WAV文件
        
        Args:
            text (str): 要转换的文本
            temperature (float): 温度参数，控制生成的随机性
            top_p (float): top-p采样参数
            top_k (int): top-k采样参数
            output_path (str, optional): 输出文件的路径，如果为None则使用默认路径
            
        Returns:
            tuple: (保存的音频文件路径, base64编码的音频数据)
        """
        try:
            # 设置推理参数
            params_infer_code = self.chat.InferCodeParams(
                spk_emb=self.spk_emb_str,
                temperature=temperature,
                top_P=top_p,
                top_K=top_k,
            )
            
            # 执行推理
            wavs = self.chat.infer([text], use_decoder = True, params_infer_code = params_infer_code)
            wav = wavs[0]
            
            # 生成输出路径
            if output_path is None:
                import tempfile
                import os
                temp_dir = tempfile.gettempdir()
                output_path = os.path.join(temp_dir, f"tts_output_{int(time.time())}.wav")
            
            # 将numpy数组转换为PyTorch张量并保存为WAV文件
            tensor_wav = torch.from_numpy(wav).unsqueeze(0)  # 添加通道维度
            torchaudio.save(output_path, tensor_wav, 24000)  # ChatTTS的采样率为24000
            
            # 将音频文件读取并转换为base64
            with open(output_path, "rb") as audio_file:
                audio_bytes = audio_file.read()
                base64_audio = base64.b64encode(audio_bytes).decode('utf-8')
            
            self.logger.info(f"文本转语音成功，已保存到: {output_path}")
            self.logger.info(f"转换的文本内容: {text[:50]}...")
            self.logger.info(f"已生成base64编码，编码长度: {len(base64_audio)}")
            
            return output_path, base64_audio
            
        except Exception as e:
            self.logger.error(f"文本转语音失败: {str(e)}")
            raise
            
    def fish_speech(self, text, voice=None, response_format="mp3"):
        """使用Fish-Speech-1.5模型将文本转换为语音
        
        Args:
            text (str): 要转换的文本
            voice (str, optional): 语音样本的路径，用于克隆声音
            response_format (str, optional): 返回音频的格式，默认为mp3
            
        Returns:
            str: base64编码的音频数据
        """
        try:
            # 获取Fish-Speech API配置
            api_url = self.config.get('tts.fish_speech.api_url', 'http://localhost:9997/v1/audio/speech')
            
            # 构建请求数据
            request_data = {
                "model": "FishSpeech-1.5",
                "input": text,
                "response_format": response_format
            }
            
            # 如果提供了声音样本，添加到请求中
            if voice:
                request_data["voice"] = voice
                
            self.logger.info(f"请求Fish-Speech API: {api_url}")
            self.logger.info(f"请求数据: {json.dumps(request_data)}")
            
            # 发送请求
            response = requests.post(api_url, json=request_data)
            
            # 检查响应状态
            if response.status_code != 200:
                error_msg = f"Fish-Speech API请求失败，状态码: {response.status_code}, 响应内容: {response.text}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
            
            # 直接获取base64编码的音频数据
            audio_base64 = response.text
            
            self.logger.info(f"Fish-Speech文本转语音成功")
            self.logger.info(f"转换的文本内容: {text[:50]}...")
            self.logger.info(f"已获取base64编码，编码长度: {len(audio_base64)}")
            
            return audio_base64
            
        except Exception as e:
            self.logger.error(f"Fish-Speech文本转语音失败: {str(e)}")
            raise 