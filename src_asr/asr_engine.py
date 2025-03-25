#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import tempfile
import numpy as np
import torch
import whisperx
import librosa
import soundfile as sf
from pydub import AudioSegment
from utils.config_loader import ConfigLoader

# 加载配置
config = ConfigLoader()
os.environ['HF_HOME'] = config.get_hf_home()

class ASREngine:
    """语音识别引擎，基于Whisper模型实现"""
    
    def __init__(self, model_size=None, logger=None):
        """初始化ASR引擎
        
        Args:
            model_size: Whisper模型大小，可选值为['tiny', 'base', 'small', 'medium', 'large']
            logger: 日志记录器，如果为None则使用print函数
        """
        # 设置日志记录器
        self.logger = logger
        
        # 加载配置
        self.config = ConfigLoader()
        
        # 如果未指定模型大小，则从配置文件中获取
        if model_size is None:
            model_size = self.config.get_model_size()
        
        # 检查是否有GPU可用
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # 对于M系列芯片的Mac，暂时不使用MPS加速，因为存在兼容性问题
        # if torch.backends.mps.is_available():
        #     self.device = "mps"
        
        if self.logger:
            self.logger.info(f"使用设备: {self.device}")
        else:
            print(f"使用设备: {self.device}")
        
        # 从配置中获取模型目录
        model_dir = self.config.get_model_dir()
        
        # 加载WhisperX模型
        self.model = whisperx.load_model(model_dir, 'cpu', compute_type='int8')
        
        if self.logger:
            self.logger.info("已加载WhisperX模型")
        else:
            print("已加载WhisperX模型")
        
        # 设置语言为中文，从配置中获取
        self.language = self.config.get_default_language()
    
    def recognize(self, audio_path):
        """识别音频文件内容
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            list: 包含识别结果的列表，每个元素为一个字典，包含文本、开始时间和结束时间
        """
        if self.logger:
            self.logger.info(f"开始识别音频: {audio_path}")
        
        # 执行转录
        result = self.model.transcribe(
            audio_path,
            language=self.language,
            batch_size=8
        )
        
        if self.logger:
            self.logger.info(f"转录完成，检测到语言: {result.get('language', self.language)}")
        
        # 使用WhisperX的对齐功能获取更精确的时间戳
        if self.logger:
            self.logger.info("开始进行音频对齐")
            
        model_a, metadata = whisperx.load_align_model(language_code=self.language, device=self.device)
        result = whisperx.align(
            result["segments"],
            model_a,
            metadata,
            audio_path,
            self.device,
            return_char_alignments=False
        )
        
        # 释放对齐模型资源
        del model_a
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        if self.logger:
            self.logger.info("音频对齐完成")
        else:
            print(f"检测到语言: {self.language}")
        
        # 处理结果
        segments = []
        for segment in result["segments"]:
            segments.append({
                "text": segment["text"].strip(),
                "start_time": segment["start"],
                "end_time": segment["end"]
            })
        
        if self.logger:
            self.logger.info(f"识别完成，共 {len(segments)} 个片段")
            
        return segments
    
    
    def recognize_with_diarize_segments(self, audio_path, session_dir=None):
        """基于diarize_segments.json文件中的时间段信息拆分音频并识别
        
        Args:
            audio_path: 音频文件路径
            session_dir: 会话目录，如果为None则创建新的目录
            
        Returns:
            list: 包含识别结果的列表，每个元素为一个字典，包含文本、开始时间、结束时间和说话人标识
        """
        self.logger.info(f"开始基于diarize_segments.json拆分音频并识别: {audio_path}")
        
        try:
            # 1. 使用传入的会话目录或创建新的会话目录
            import tempfile
            import json  # 确保在方法开始时就导入json模块
            from utils.temp_manager import TempManager
            from pathlib import Path
            import traceback
            
            temp_manager = TempManager()
            if session_dir is None:
                # 如果没有提供会话目录，则创建一个新的
                session_dir = temp_manager.create_session_dir()
                self.logger.info(f"创建新的会话目录用于保存中间结果: {session_dir}")
            else:
                self.logger.info(f"使用提供的会话目录: {session_dir}")
            
            # 创建speaker_segments目录
            speaker_segments_dir = os.path.join(session_dir, "speaker_segments")
            os.makedirs(speaker_segments_dir, exist_ok=True)
            self.logger.info(f"创建speaker_segments目录: {speaker_segments_dir}")
            
            # 查找diarize_segments.json文件
            self.logger.info(f"在当前会话目录查找diarize_segments.json文件: {session_dir}")
            diarize_segments_path = os.path.join(session_dir, "diarize_segments.json")

            # 检查文件是否存在
            if not os.path.exists(diarize_segments_path):
                self.logger.info("当前会话目录中未找到diarize_segments.json文件，将生成新文件")
                
                # 尝试使用pyannote.audio进行说话人分离
                try:
                    import torch
                    from pyannote.audio import Pipeline
                    from pyannote.core import Annotation
                    
                    # 检查音频文件是否存在和可访问
                    if not os.path.exists(audio_path):
                        raise FileNotFoundError(f"音频文件不存在: {audio_path}")
                    
                    # 使用pyannote.audio进行说话人分离
                    auth_token = self.config.get_hf_token()
                    self.logger.info("加载pyannote/speaker-diarization-3.1模型")
                    
                    diarize_pipeline = Pipeline.from_pretrained(
                        "pyannote/speaker-diarization-3.1",
                        use_auth_token=auth_token
                    ).to(torch.device(self.device))
                    
                    # 设置固定说话人数量
                    num_speakers = self.config.get_num_speakers()
                    self.logger.info(f"执行说话人分离，固定说话人数量为{num_speakers}")
                    diarization = diarize_pipeline(audio_path, num_speakers=num_speakers)
                    
                    # 创建diarize_segments格式
                    diarize_segments = {"segments": []}
                    segment_count = 0
                    
                    # 记录分离的片段信息
                    for segment, _, speaker in diarization.itertracks(yield_label=True):
                        segment_count += 1
                        # 确保时间戳合理
                        start_time = max(0, segment.start)
                        end_time = max(start_time + 0.1, segment.end)  # 确保片段至少有0.1秒
                        
                        diarize_segments["segments"].append({
                            "speaker": speaker,
                            "start": start_time,
                            "end": end_time
                        })
                    
                    self.logger.info(f"说话人分离完成，共分离出 {segment_count} 个片段")
                    
                    # 如果没有分离出任何片段，创建两个默认片段
                    if segment_count == 0:
                        self.logger.warning("未分离出任何说话人片段，创建默认片段")
                        # 估计音频长度
                        import librosa
                        audio_length = librosa.get_duration(path=audio_path)
                        mid_point = audio_length / 2
                        
                        # 创建两个默认片段
                        diarize_segments["segments"] = [
                            {"speaker": "SPEAKER_00", "start": 0, "end": mid_point},
                            {"speaker": "SPEAKER_01", "start": mid_point, "end": audio_length}
                        ]
                        segment_count = 2
                        self.logger.info(f"创建了 {segment_count} 个默认片段，音频长度: {audio_length}秒")
                    
                    # 保存diarize_segments结果
                    with open(diarize_segments_path, 'w', encoding='utf-8') as f:
                        json.dump(diarize_segments, f, ensure_ascii=False, indent=2)
                    self.logger.info(f"说话人分离结果已保存至: {diarize_segments_path}")
                    
                except Exception as e:
                    self.logger.error(f"使用pyannote进行说话人分离失败: {str(e)}")
                    self.logger.error(traceback.format_exc())
                    
                    # 尝试使用简单的能量分离方法作为备选
                    self.logger.info("尝试使用简单的能量分离方法作为备选")
                    try:
                        # 估计音频长度
                        import librosa
                        audio_length = librosa.get_duration(path=audio_path)
                        
                        # 创建能量分离的片段
                        y, sr = librosa.load(audio_path, sr=None)
                        
                        # 计算能量
                        frame_length = int(sr * 0.025)  # 25ms帧长
                        hop_length = int(sr * 0.01)    # 10ms帧移
                        energy = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
                        
                        # 计算能量阈值
                        energy_threshold = np.median(energy) * 1.2  # 略高于中位数的阈值
                        
                        # 分割片段
                        segments = []
                        is_speech = False
                        start_time = 0
                        min_segment_length = 0.5  # 最小片段长度(秒)
                        
                        for i, e in enumerate(energy):
                            time = i * hop_length / sr
                            
                            if not is_speech and e > energy_threshold:
                                # 从非语音变为语音
                                is_speech = True
                                start_time = time
                            elif is_speech and (e <= energy_threshold or i == len(energy) - 1):
                                # 从语音变为非语音，或者到达结尾
                                is_speech = False
                                end_time = time
                                
                                # 只保留足够长的片段
                                if end_time - start_time >= min_segment_length:
                                    speaker = f"SPEAKER_{len(segments) % 2:02d}"
                                    segments.append({
                                        "speaker": speaker,
                                        "start": start_time,
                                        "end": end_time
                                    })
                        
                        # 如果没有分离出任何片段，创建默认片段
                        if not segments:
                            mid_point = audio_length / 2
                            segments = [
                                {"speaker": "SPEAKER_00", "start": 0, "end": mid_point},
                                {"speaker": "SPEAKER_01", "start": mid_point, "end": audio_length}
                            ]
                            
                        # 保存为diarize_segments.json
                        diarize_segments = {"segments": segments}
                        with open(diarize_segments_path, 'w', encoding='utf-8') as f:
                            json.dump(diarize_segments, f, ensure_ascii=False, indent=2)
                        self.logger.info(f"使用简单能量分离，共分离出 {len(segments)} 个片段，结果已保存至: {diarize_segments_path}")
                        
                    except Exception as backup_error:
                        self.logger.error(f"备选的能量分离方法也失败: {str(backup_error)}")
                        self.logger.error(traceback.format_exc())
                        raise FileNotFoundError("无法生成diarize_segments.json文件")

            if not os.path.exists(diarize_segments_path):
                raise FileNotFoundError(f"找不到或无法创建diarize_segments.json文件: {diarize_segments_path}")

            self.logger.info(f"使用diarize_segments.json文件: {diarize_segments_path}")

            # 读取diarize_segments.json文件
            try:
                with open(diarize_segments_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 清理可能的错误字符
                    content = content.replace('ç', '')
                    content = content.replace(',}', '}')
                    content = content.replace(',]', ']')
                    # 解析JSON
                    diarize_data = json.loads(content)
                    
                segments = diarize_data.get("segments", [])
                self.logger.info(f"读取到 {len(segments)} 个分段信息")
            except Exception as e:
                self.logger.error(f"解析diarize_segments.json失败: {str(e)}")
                self.logger.error(traceback.format_exc())
                segments = []
            
            if not segments:
                self.logger.error("diarize_segments.json中没有有效的分段信息")
                # 如果没有分段信息，则使用整体识别模式作为备选
                return self.recognize(audio_path)
            
            # 2. 从音频文件中提取每个片段并进行识别
            from src_asr.audio_segment_extractor import AudioSegmentExtractor
            extractor = AudioSegmentExtractor(temp_manager)
            
            results = []
            successful_segments = 0
            failed_segments = 0
            
            for i, segment in enumerate(segments):
                speaker = segment.get("speaker", f"SPEAKER_{i % 2:02d}")
                start_time = segment.get("start", 0)
                end_time = segment.get("end", 0)
                
                # 转换为易读的说话人标识
                readable_speaker = speaker
                if speaker == "SPEAKER_00":
                    readable_speaker = "speakerA"
                elif speaker == "SPEAKER_01":
                    readable_speaker = "speakerB"
                elif speaker.startswith("SPEAKER_"):
                    # 提取数字部分并转换为字母
                    try:
                        num = int(speaker.split("_")[1])
                        readable_speaker = f"speaker{chr(65 + (num % 26))}"
                    except (ValueError, IndexError):
                        readable_speaker = speaker
                
                if end_time <= start_time:
                    self.logger.warning(f"无效的时间段: {start_time} - {end_time}，跳过")
                    failed_segments += 1
                    continue
                
                # 时间段太短可能会导致识别问题，设置最小间隔
                if end_time - start_time < 0.1:
                    self.logger.warning(f"时间段过短: {start_time} - {end_time}，跳过")
                    failed_segments += 1
                    continue
                
                self.logger.info(f"处理片段 {i+1}/{len(segments)}: {readable_speaker} {start_time:.2f}s - {end_time:.2f}s")
                
                # 提取音频片段
                try:
                    segment_file = extractor.extract_segment(
                        audio_path, 
                        start_time, 
                        end_time, 
                        session_dir=speaker_segments_dir,
                        speaker_id=speaker
                    )
                    
                    if not segment_file or not os.path.exists(segment_file):
                        self.logger.error(f"提取片段失败: {start_time} - {end_time}")
                        failed_segments += 1
                        continue
                    
                    # 识别音频片段
                    self.logger.info(f"开始识别片段: {segment_file}")
                    segment_result = self.recognize(segment_file)
                    
                    # 如果没有识别结果，则跳过
                    if not segment_result:
                        self.logger.warning(f"片段没有识别结果: {segment_file}")
                        failed_segments += 1
                        continue
                    
                    # 合并片段中的所有文本
                    text_parts = [item["text"] for item in segment_result if item["text"].strip()]
                    combined_text = " ".join(text_parts)
                    
                    if not combined_text.strip():
                        self.logger.warning(f"片段没有有效文本: {segment_file}")
                        failed_segments += 1
                        continue
                    
                    # 添加到结果中
                    results.append({
                        "speaker": readable_speaker,
                        "original_speaker": speaker,
                        "text": combined_text,
                        "start_time": start_time,
                        "end_time": end_time,
                        "segment_path": segment_file,
                        "confidence": 1.0  # 默认置信度
                    })
                    
                    self.logger.info(f"片段识别成功: {readable_speaker} {start_time:.2f}s - {end_time:.2f}s: {combined_text[:30]}...")
                    successful_segments += 1
                    
                except Exception as e:
                    self.logger.error(f"处理片段时出错: {str(e)}")
                    self.logger.error(traceback.format_exc())
                    failed_segments += 1
            
            # 按时间戳排序
            results.sort(key=lambda x: x["start_time"])
            
            # 记录处理统计信息
            self.logger.info(f"所有片段处理完成，共 {len(segments)} 个片段，成功: {successful_segments}，失败: {failed_segments}")
            
            # 保存最终结果
            final_results_path = os.path.join(session_dir, "diarize_segments_results.json")
            with open(final_results_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            self.logger.info(f"结果已保存至: {final_results_path}")
            
            # 生成摘要文本
            summary_path = os.path.join(session_dir, "diarize_segments_summary.txt")
            with open(summary_path, 'w', encoding='utf-8') as f:
                for item in results:
                    f.write(f"[{item['speaker']}] {item['start_time']:.2f}s - {item['end_time']:.2f}s: {item['text']}\n")
            self.logger.info(f"摘要已保存至: {summary_path}")
            
            # 如果没有有效结果，回退到简单识别
            if not results:
                self.logger.warning("未能获取有效结果，回退到整体识别模式")
                return self.recognize(audio_path)
            
            return results
            
        except Exception as e:
            self.logger.error(f"处理过程中出错: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            # 如果处理失败，则使用原始识别模式作为备选
            return self.recognize(audio_path)
    
    def _simple_speaker_separation(self, segments, audio_path):
        """简单的说话人分离方法，基于能量和频率特征
        
        Args:
            segments: 识别结果列表
            audio_path: 音频文件路径
        """
        if self.logger:
            self.logger.info(f"使用简单的能量分离方法进行说话人分离: {audio_path}")
        
        # 加载音频
        y, sr = librosa.load(audio_path, sr=None)
        
        # 提取特征
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        
        # 计算所有段落的能量，用于自适应阈值
        energies = []
        for segment in segments:
            start_sample = int(segment["start_time"] * sr)
            end_sample = int(segment["end_time"] * sr)
            
            # 确保索引在有效范围内
            if start_sample >= len(y):
                start_sample = len(y) - 1
            if end_sample >= len(y):
                end_sample = len(y) - 1
            
            if end_sample > start_sample:
                segment_audio = y[start_sample:end_sample]
                energy = np.mean(librosa.feature.rms(y=segment_audio)[0])
                energies.append(energy)
        
        # 计算能量的中位数作为自适应阈值
        if energies:
            energy_threshold = np.median(energies)
            if self.logger:
                self.logger.info(f"能量自适应阈值: {energy_threshold}")
        else:
            energy_threshold = 0.05  # 默认阈值
            if self.logger:
                self.logger.info(f"使用默认能量阈值: {energy_threshold}")
        
        # 简单聚类，将段落分为两类说话人
        for i, segment in enumerate(segments):
            start_sample = int(segment["start_time"] * sr)
            end_sample = int(segment["end_time"] * sr)
            
            # 确保索引在有效范围内
            if start_sample >= len(y):
                start_sample = len(y) - 1
            if end_sample >= len(y):
                end_sample = len(y) - 1
            
            # 提取这段音频的特征
            if end_sample > start_sample:
                segment_audio = y[start_sample:end_sample]
                energy = np.mean(librosa.feature.rms(y=segment_audio)[0])
                
                # 基于能量简单区分说话人
                if energy > energy_threshold:
                    segment["speaker"] = "speakerA"
                else:
                    segment["speaker"] = "speakerB"
            else:
                # 处理边界情况，使用前一个段落的说话人或默认值
                if i > 0 and "speaker" in segments[i-1]:
                    segment["speaker"] = segments[i-1]["speaker"]
                else:
                    segment["speaker"] = "speakerA"
            
            # 确保所有段落都有说话人标识
            if "speaker" not in segment:
                segment["speaker"] = f"speaker{'A' if i % 2 == 0 else 'B'}"
        
        if self.logger:
            self.logger.info(f"简单能量分离完成，共处理 {len(segments)} 个片段")
            
        return segments