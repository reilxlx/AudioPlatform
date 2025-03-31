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
import pandas as pd
import os

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
            tuple: (本地保存的音频文件路径, base64编码的音频数据)
        """
        try:
            # 获取Fish-Speech API配置
            api_url = self.config.get_nested('tts.fish_speech.api_url')
            if not api_url:
                api_url = 'http://localhost:9997/v1/audio/speech'
                self.logger.warning(f"未找到Fish-Speech API URL配置，使用默认值: {api_url}")
            
            self.logger.info(f"使用Fish-Speech API: {api_url}")
            
            # 构建请求数据
            request_data = {
                "model": "FishSpeech-1.5",
                "input": text,
                "response_format": response_format
            }
            
            # 如果提供了声音样本，添加到请求中
            if voice:
                # 检查声音样本文件是否存在
                import os
                if not os.path.exists(voice):
                    self.logger.warning(f"声音样本文件不存在: {voice}，将使用默认音色")
                else:
                    request_data["voice"] = voice
                
            self.logger.info(f"请求Fish-Speech API: {api_url}")
            # 使用ensure_ascii=False确保中文能够正确显示而不是Unicode转义序列
            self.logger.info(f"请求数据: {json.dumps(request_data, ensure_ascii=False)}")
            
            # 发送请求
            try:
                response = requests.post(api_url, json=request_data, timeout=300)
            except requests.exceptions.RequestException as e:
                error_msg = f"请求Fish-Speech API失败: {str(e)}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
            
            # 检查响应状态
            if response.status_code != 200:
                error_msg = f"Fish-Speech API请求失败，状态码: {response.status_code}, 响应内容: {response.text[:200] if hasattr(response, 'text') else '无文本响应'}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
            
            # 获取二进制音频数据
            audio_binary = response.content
            
            # 检查返回的二进制数据
            if not audio_binary or len(audio_binary) < 100:  # 简单检查返回数据是否有效
                error_msg = f"Fish-Speech API返回的数据无效，长度: {len(audio_binary) if audio_binary else 0}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
            
            # 生成输出文件路径
            import os
            import tempfile
            temp_dir = os.path.join("temp_files", "fish_speech")
            os.makedirs(temp_dir, exist_ok=True)
            output_path = os.path.join(temp_dir, f"fish_speech_output_{int(time.time())}.{response_format}")
            
            # 直接保存二进制音频数据到文件
            try:
                with open(output_path, "wb") as f:
                    f.write(audio_binary)
                self.logger.info(f"已将音频保存到: {output_path}, 大小: {len(audio_binary)} 字节")
            except Exception as e:
                error_msg = f"保存音频文件失败: {str(e)}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
            
            # 将二进制数据转换为base64编码以便JSON响应
            audio_base64 = base64.b64encode(audio_binary).decode('utf-8')
            
            self.logger.info(f"Fish-Speech文本转语音成功，音频已保存到: {output_path}")
            self.logger.info(f"转换的文本内容: {text[:50]}...")
            self.logger.info(f"已生成base64编码，编码长度: {len(audio_base64)}")
            
            return output_path, audio_base64
            
        except Exception as e:
            self.logger.error(f"Fish-Speech文本转语音失败: {str(e)}")
            raise
    
    def xinference_chat_tts(self, text, voice="2155", response_format="mp3"):
        """使用xinference部署的ChatTTS模型将文本转换为语音
        
        Args:
            text (str): 要转换的文本
            voice (str, optional): 音色ID或音色嵌入数据，默认为"2155"
            response_format (str, optional): 返回音频的格式，默认为mp3
            
        Returns:
            tuple: (本地保存的音频文件路径, base64编码的音频数据)
        """
        try:
            start_time = time.time()
            
            # 获取Xinference API地址
            api_url = self.config.get_nested('tts.xinference.api_url')
            if not api_url:
                api_url = 'http://localhost:9997/v1/audio/speech'
                self.logger.warning(f"未找到Xinference API URL配置，使用默认值: {api_url}")
            
            self.logger.info(f"使用Xinference ChatTTS API: {api_url}")
            
            # 处理音色参数
            voice_data = voice
            
            # 如果voice是seed_id (如 "2155")，从CSV文件中获取对应的嵌入数据
            if isinstance(voice, str) and voice.isdigit():
                try:
                    # 从CSV文件中读取嵌入数据
                    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                           "evaluation_results.csv")
                    self.logger.info(f"从CSV文件获取音色数据: {csv_path}")
                    
                    df = pd.read_csv(csv_path)
                    seed_id = f"seed_{voice}"
                    row = df[df['seed_id'] == seed_id]
                    
                    if not row.empty:
                        voice_data = row.iloc[0]["emb_data"]
                        self.logger.info(f"找到音色 {seed_id} 的嵌入数据，长度: {len(voice_data) if voice_data else 0}")
                    else:
                        self.logger.warning(f"未在CSV文件中找到音色ID: {seed_id}，将使用默认音色")
                        # 如果找不到对应音色，使用默认音色
                        if self.spk_emb_str:
                            voice_data = self.spk_emb_str
                except Exception as e:
                    self.logger.error(f"读取音色数据失败: {str(e)}，将使用默认音色")
                    # 如果读取失败，使用默认音色
                    if self.spk_emb_str:
                        voice_data = self.spk_emb_str
            
            # 构建请求数据
            request_data = {
                "model": "ChatTTS",
                "input": text,
                "voice": voice_data,
                "response_format": response_format
            }
            
            # 记录请求信息（不包含完整的voice数据，可能很长）
            log_request_data = {
                "model": "ChatTTS",
                "input": text[:50] + ("..." if len(text) > 50 else ""),
                "voice": self._format_voice_data(voice_data),
                "response_format": response_format
            }
            self.logger.info(f"Xinference ChatTTS请求数据: {json.dumps(log_request_data, ensure_ascii=False)}")
            
            # 发送请求
            try:
                response = requests.post(api_url, json=request_data, timeout=300)
            except requests.exceptions.RequestException as e:
                error_msg = f"请求Xinference ChatTTS API失败: {str(e)}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
            
            # 检查响应状态
            if response.status_code != 200:
                error_msg = f"Xinference ChatTTS API请求失败，状态码: {response.status_code}, 响应内容: {response.text[:200] if hasattr(response, 'text') else '无文本响应'}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
            
            # 获取二进制音频数据
            audio_binary = response.content
            
            # 检查返回的二进制数据
            if not audio_binary or len(audio_binary) < 100:  # 简单检查返回数据是否有效
                error_msg = f"Xinference ChatTTS API返回的数据无效，长度: {len(audio_binary) if audio_binary else 0}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
            
            # 生成输出文件路径
            temp_dir = os.path.join("temp_files", "xinference_chat_tts")
            os.makedirs(temp_dir, exist_ok=True)
            output_path = os.path.join(temp_dir, f"chat_tts_output_{int(time.time())}.{response_format}")
            
            # 直接保存二进制音频数据到文件
            try:
                with open(output_path, "wb") as f:
                    f.write(audio_binary)
                self.logger.info(f"已将音频保存到: {output_path}, 大小: {len(audio_binary)} 字节")
            except Exception as e:
                error_msg = f"保存音频文件失败: {str(e)}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
            
            # 将二进制数据转换为base64编码以便JSON响应
            audio_base64 = base64.b64encode(audio_binary).decode('utf-8')
            
            # 计算处理时间
            process_time = time.time() - start_time
            
            self.logger.info(f"Xinference ChatTTS文本转语音成功，音频已保存到: {output_path}")
            self.logger.info(f"转换的文本内容: {text[:50]}...")
            self.logger.info(f"处理时间: {process_time:.2f}秒")
            self.logger.info(f"已生成base64编码，编码长度: {len(audio_base64)}")
            
            return output_path, audio_base64
            
        except Exception as e:
            self.logger.error(f"Xinference ChatTTS文本转语音失败: {str(e)}")
            raise

    def _format_voice_data(self, voice_data):
        """格式化 voice 数据以便于日志显示，显示最前和最后的 50 个字符
        
        Args:
            voice_data: 音色数据
            
        Returns:
            str: 格式化后的音色数据描述
        """
        if voice_data is None:
            return "None"
            
        voice_str = str(voice_data)
        total_len = len(voice_str)
        
        if total_len <= 100:
            return voice_str
        else:
            return f"{voice_str[:200]}...{voice_str[-200:]} (总长度: {total_len})"