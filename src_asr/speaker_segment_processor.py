#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import torch
import whisperx
import gc
from src_asr.audio_segment_extractor import AudioSegmentExtractor
from utils.temp_manager import TempManager

class SpeakerSegmentProcessor:
    """说话人分段处理器，用于基于说话人分离结果进行音频分段识别"""
    
    def __init__(self, asr_engine, logger=None):
        """初始化说话人分段处理器
        
        Args:
            asr_engine: ASR引擎实例
            logger: 日志记录器
        """
        self.asr_engine = asr_engine
        self.logger = logger or asr_engine.logger
        self.temp_manager = TempManager()
        self.segment_extractor = AudioSegmentExtractor(self.temp_manager)
    
    def process_segments(self, audio_path, diarize_segments_path, session_dir):
        """处理说话人分段，提取音频片段并进行识别
        
        Args:
            audio_path: 音频文件路径
            diarize_segments_path: 说话人分离结果文件路径
            session_dir: 会话目录
            
        Returns:
            list: 包含识别结果的列表，每个元素为一个字典，包含文本、开始时间、结束时间和说话人标识
        """
        # 读取说话人分离结果
        try:
            with open(diarize_segments_path, 'r', encoding='utf-8') as f:
                # 读取文件内容
                content = f.read()
                # 清理可能的错误字符
                content = content.replace('ç', '')
                content = content.replace(',}', '}')
                content = content.replace(',]', ']')
                # 解析JSON
                diarize_segments = json.loads(content)
        except json.JSONDecodeError as e:
            self.logger.error(f"解析diarize_segments.json失败: {str(e)}")
            # 创建一个空的segments列表
            diarize_segments = {"segments": []}
        except Exception as e:
            self.logger.error(f"读取diarize_segments.json失败: {str(e)}")
            # 创建一个空的segments列表
            diarize_segments = {"segments": []}
        
        # 创建片段目录
        segments_dir = os.path.join(session_dir, "speaker_segments")
        os.makedirs(segments_dir, exist_ok=True)
        
        # 确认diarize_segments.json格式正确
        if not isinstance(diarize_segments, dict) or "segments" not in diarize_segments:
            self.logger.error("diarize_segments.json格式不正确，应包含'segments'字段")
            # 创建一个空的segments列表
            diarize_segments = {"segments": []}
            
        # 提取音频片段
        self.logger.info("开始根据说话人分离结果提取音频片段")
        try:
            segment_files = self.segment_extractor.extract_segments_from_diarization(
                audio_path, 
                diarize_segments, 
                segments_dir  # 直接传入speaker_segments目录
            )
            self.logger.info(f"共提取了 {len(segment_files)} 个音频片段")
        except Exception as e:
            self.logger.error(f"提取音频片段失败: {str(e)}")
            # 如果提取失败，返回空结果
            return []
        
        # 对每个片段单独进行识别
        self.logger.info("开始对每个片段单独进行识别")
        segment_results = []
        
        for segment_info in segment_files:
            speaker = segment_info["speaker"]
            start_time = segment_info["start_time"]
            end_time = segment_info["end_time"]
            segment_path = segment_info["audio_path"]
            
            self.logger.info(f"识别片段: {speaker}, {start_time:.2f}s - {end_time:.2f}s, 路径: {segment_path}")
            
            try:
                # 执行转录
                result = self.asr_engine.model.transcribe(
                    segment_path,
                    language=self.asr_engine.language,
                    batch_size=8
                )
                
                # 使用WhisperX的对齐功能获取更精确的时间戳
                try:
                    model_a, metadata = whisperx.load_align_model(language_code=self.asr_engine.language, device=self.asr_engine.device)
                    aligned_result = whisperx.align(
                        result["segments"],
                        model_a,
                        metadata,
                        segment_path,
                        self.asr_engine.device,
                        return_char_alignments=False
                    )
                    
                    # 释放对齐模型资源
                    del model_a
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    
                    # 处理结果 - 优化文本处理逻辑，保留更多细节信息
                    segment_text = ""
                    segment_words = []
                    
                    # 收集所有单词和它们的时间戳
                    if "segments" in aligned_result and aligned_result["segments"]:
                        for seg in aligned_result["segments"]:
                            segment_text += seg["text"].strip() + " "
                            
                            # 如果有单词级别的时间戳，保存它们
                            if "words" in seg and seg["words"]:
                                # 调整单词时间戳，加上片段的开始时间作为偏移
                                for word in seg["words"]:
                                    adjusted_word = word.copy()
                                    adjusted_word["start"] = word["start"] + start_time
                                    adjusted_word["end"] = word["end"] + start_time
                                    segment_words.append(adjusted_word)
                except Exception as align_error:
                    self.logger.warning(f"对齐过程失败，使用原始转录结果: {str(align_error)}")
                    # 如果对齐失败，使用原始转录结果
                    segment_text = ""
                    segment_words = []
                    if "segments" in result:
                        for seg in result["segments"]:
                            segment_text += seg["text"].strip() + " "
                
                # 将说话人标识转换为可读格式
                readable_speaker = self._convert_speaker_id(speaker)
                
                # 添加到结果列表，增强结果数据结构
                segment_result = {
                    "text": segment_text.strip(),
                    "start_time": start_time,
                    "end_time": end_time,
                    "speaker": readable_speaker,
                    "original_speaker": speaker,
                    "confidence": result.get("detection_score", 1.0),  # 添加置信度
                    "words": segment_words if segment_words else [],  # 添加单词级别的时间戳
                    "segment_path": segment_path  # 保存片段文件路径
                }
                
                segment_results.append(segment_result)
                self.logger.info(f"识别结果: {segment_text.strip()}")
                
            except Exception as e:
                self.logger.error(f"识别片段失败: {str(e)}")
                # 如果识别失败，添加空结果
                segment_results.append({
                    "text": "",
                    "start_time": start_time,
                    "end_time": end_time,
                    "speaker": self._convert_speaker_id(speaker),
                    "original_speaker": speaker,
                    "error": str(e),
                    "segment_path": segment_path  # 保存片段文件路径
                })
        
        # 按时间戳排序
        segment_results.sort(key=lambda x: x["start_time"])
        
        # 保存最终处理结果
        final_segments_path = os.path.join(session_dir, "speaker_segment_results.json")
        with open(final_segments_path, 'w', encoding='utf-8') as f:
            json.dump(segment_results, f, ensure_ascii=False, indent=2)
        self.logger.info(f"最终处理结果已保存至: {final_segments_path}")
        
        # 生成话者分离摘要文本
        summary_path = os.path.join(session_dir, "speaker_segment_summary.txt")
        with open(summary_path, 'w', encoding='utf-8') as f:
            for segment in segment_results:
                f.write(f"[{segment['speaker']}] {segment['start_time']:.1f}s - {segment['end_time']:.1f}s: {segment['text']}\n")
        self.logger.info(f"话者分离摘要已保存至: {summary_path}")
        
        # 分组处理说话人，便于日志查看
        speaker_groups = {}
        for segment in segment_results:
            speaker = segment.get('speaker', 'UNKNOWN')
            speaker_groups.setdefault(speaker, []).append(segment)
        
        # 记录每个说话人的片段数量
        for speaker, speaker_segments in speaker_groups.items():
            self.logger.info(f"说话人 {speaker}: {len(speaker_segments)} 个片段")
        
        self.logger.info(f"处理完成，共识别出 {len(segment_results)} 个片段")
        return segment_results
    
    def process_segments_from_alignment(self, audio_path, alignment_result_path, session_dir):
        """通过alignment_result.json处理音频片段，提取并识别
        
        Args:
            audio_path: 音频文件路径
            alignment_result_path: alignment_result.json文件路径
            session_dir: 会话目录
            
        Returns:
            list: 包含识别结果的列表
        """
        # 读取对齐结果
        with open(alignment_result_path, 'r', encoding='utf-8') as f:
            alignment_result = json.load(f)
        
        # 创建片段目录
        segments_dir = os.path.join(session_dir, "speaker_segments")
        os.makedirs(segments_dir, exist_ok=True)
        
        # 提取音频片段
        self.logger.info("开始根据alignment结果提取音频片段")
        
        segment_files = []
        for i, segment in enumerate(alignment_result.get("segments", [])):
            start_time = segment.get("start", 0)
            end_time = segment.get("end", 0)
            
            # 默认speaker为未知，后面会通过话者分离分配
            speaker_id = f"SEGMENT_{i:03d}"
            
            # 提取音频片段
            segment_path = self.segment_extractor.extract_segment(
                audio_path, 
                start_time, 
                end_time, 
                segments_dir, 
                speaker_id
            )
            
            # 添加到结果列表
            segment_files.append({
                "index": i,
                "speaker": speaker_id,  # 临时speaker标识
                "start_time": start_time,
                "end_time": end_time,
                "audio_path": segment_path,
                "original_text": segment.get("text", "")  # 保存原始文本用于对比
            })
        
        self.logger.info(f"共提取了 {len(segment_files)} 个音频片段")
        
        # 对每个片段单独进行识别
        self.logger.info("开始对每个片段单独进行识别")
        segment_results = []
        
        for segment_info in segment_files:
            index = segment_info["index"]
            start_time = segment_info["start_time"]
            end_time = segment_info["end_time"]
            segment_path = segment_info["audio_path"]
            original_text = segment_info["original_text"]
            
            self.logger.info(f"识别片段: {index}, {start_time:.2f}s - {end_time:.2f}s")
            
            try:
                # 执行转录
                result = self.asr_engine.model.transcribe(
                    segment_path,
                    language=self.asr_engine.language,
                    batch_size=8
                )
                
                # 使用WhisperX的对齐功能获取更精确的时间戳
                try:
                    model_a, metadata = whisperx.load_align_model(language_code=self.asr_engine.language, device=self.asr_engine.device)
                    aligned_result = whisperx.align(
                        result["segments"],
                        model_a,
                        metadata,
                        segment_path,
                        self.asr_engine.device,
                        return_char_alignments=False
                    )
                    
                    # 释放对齐模型资源
                    del model_a
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    
                    # 使用对齐后的结果
                    segment_text = ""
                    segment_words = []
                    
                    # 收集所有单词和它们的时间戳
                    if "segments" in aligned_result and aligned_result["segments"]:
                        for seg in aligned_result["segments"]:
                            segment_text += seg["text"].strip() + " "
                            
                            # 如果有单词级别的时间戳，保存它们
                            if "words" in seg and seg["words"]:
                                # 调整单词时间戳，加上片段的开始时间作为偏移
                                for word in seg["words"]:
                                    adjusted_word = word.copy()
                                    adjusted_word["start"] = word["start"] + start_time
                                    adjusted_word["end"] = word["end"] + start_time
                                    segment_words.append(adjusted_word)
                except Exception as align_error:
                    self.logger.warning(f"对齐过程失败，使用原始转录结果: {str(align_error)}")
                    # 如果对齐失败，使用原始转录结果
                    segment_text = ""
                    segment_words = []
                    if "segments" in result:
                        for seg in result["segments"]:
                            segment_text += seg["text"].strip() + " "
                
                # 添加到结果列表
                segment_result = {
                    "text": segment_text.strip() if segment_text else original_text,
                    "original_text": original_text,
                    "start_time": start_time,
                    "end_time": end_time,
                    "segment_path": segment_path,
                    "index": index,
                    "confidence": result.get("detection_score", 1.0),
                    "words": segment_words if segment_words else []
                }
                
                segment_results.append(segment_result)
                self.logger.info(f"识别结果: {segment_text.strip()}")
                self.logger.info(f"原始文本: {original_text}")
                
            except Exception as e:
                self.logger.error(f"识别片段失败: {str(e)}")
                # 如果识别失败，添加空结果但保留原始文本
                segment_results.append({
                    "text": original_text,  # 备用使用原始文本
                    "original_text": original_text,
                    "start_time": start_time,
                    "end_time": end_time,
                    "segment_path": segment_path,
                    "index": index,
                    "error": str(e)
                })
        
        # 按时间戳排序
        segment_results.sort(key=lambda x: x["start_time"])
        
        # 保存最终处理结果
        final_segments_path = os.path.join(session_dir, "alignment_segment_results.json")
        with open(final_segments_path, 'w', encoding='utf-8') as f:
            json.dump(segment_results, f, ensure_ascii=False, indent=2)
        self.logger.info(f"最终处理结果已保存至: {final_segments_path}")
        
        # 生成摘要文本
        summary_path = os.path.join(session_dir, "alignment_segment_summary.txt")
        with open(summary_path, 'w', encoding='utf-8') as f:
            for segment in segment_results:
                f.write(f"[Segment {segment['index']}] {segment['start_time']:.1f}s - {segment['end_time']:.1f}s:\n")
                f.write(f"  原文: {segment['original_text']}\n")
                f.write(f"  识别: {segment['text']}\n\n")
        self.logger.info(f"片段摘要已保存至: {summary_path}")
        
        self.logger.info(f"处理完成，共识别出 {len(segment_results)} 个片段")
        return segment_results
    
    def _convert_speaker_id(self, speaker):
        """将说话人ID转换为可读格式
        
        Args:
            speaker: 原始说话人ID
            
        Returns:
            str: 可读格式的说话人ID
        """
        if speaker == "SPEAKER_00":
            return "speakerA"
        elif speaker == "SPEAKER_01":
            return "speakerB"
        elif speaker.startswith("SPEAKER_"):
            # 提取数字部分并转换为字母
            try:
                num = int(speaker.split("_")[1])
                return f"speaker{chr(65 + (num % 26))}"
            except (ValueError, IndexError):
                return speaker
        return speaker


def process_speaker_segments(asr_engine, audio_path, diarize_segments_path, session_dir):
    """处理说话人分段的便捷函数
    
    Args:
        asr_engine: ASR引擎实例
        audio_path: 音频文件路径
        diarize_segments_path: 说话人分离结果文件路径
        session_dir: 会话目录
        
    Returns:
        list: 包含识别结果的列表
    """
    processor = SpeakerSegmentProcessor(asr_engine)
    return processor.process_segments(audio_path, diarize_segments_path, session_dir)


def process_alignment_segments(asr_engine, audio_path, alignment_result_path, session_dir):
    """处理对齐片段的便捷函数
    
    Args:
        asr_engine: ASR引擎实例
        audio_path: 音频文件路径
        alignment_result_path: alignment_result.json文件路径
        session_dir: 会话目录
        
    Returns:
        list: 包含识别结果的列表
    """
    processor = SpeakerSegmentProcessor(asr_engine)
    return processor.process_segments_from_alignment(audio_path, alignment_result_path, session_dir)