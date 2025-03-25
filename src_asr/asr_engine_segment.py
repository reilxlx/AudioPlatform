#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import torch
import whisperx
import gc
from src_asr.audio_segment_extractor import AudioSegmentExtractor
from utils.temp_manager import TempManager

def recognize_segments_separately(asr_engine, audio_path, diarize_segments_path, session_dir):
    """根据说话人分离结果切分音频并单独识别
    
    Args:
        asr_engine: ASR引擎实例
        audio_path: 音频文件路径
        diarize_segments_path: 说话人分离结果文件路径
        session_dir: 会话目录
        
    Returns:
        list: 包含识别结果的列表，每个元素为一个字典，包含文本、开始时间、结束时间和说话人标识
    """
    # 初始化日志记录器
    logger = asr_engine.logger
    
    # 创建音频片段提取器
    temp_manager = TempManager()
    segment_extractor = AudioSegmentExtractor(temp_manager)
    
    # 读取说话人分离结果
    with open(diarize_segments_path, 'r', encoding='utf-8') as f:
        diarize_segments = json.load(f)
    
    # 创建片段目录
    segments_dir = os.path.join(session_dir, "segments_recognition")
    os.makedirs(segments_dir, exist_ok=True)
    
    # 提取音频片段
    logger.info("开始根据说话人分离结果提取音频片段")
    segment_files = segment_extractor.extract_segments_from_diarization(
        audio_path, 
        diarize_segments, 
        segments_dir
    )
    logger.info(f"共提取了 {len(segment_files)} 个音频片段")
    
    # 对每个片段单独进行识别
    logger.info("开始对每个片段单独进行识别")
    all_segments = []
    
    # 保存每个片段的识别结果
    segment_results = []
    
    for segment_info in segment_files:
        speaker = segment_info["speaker"]
        start_time = segment_info["start_time"]
        end_time = segment_info["end_time"]
        segment_path = segment_info["audio_path"]
        
        logger.info(f"识别片段: {speaker}, {start_time:.2f}s - {end_time:.2f}s")
        
        try:
            # 执行转录
            result = asr_engine.model.transcribe(
                segment_path,
                language=asr_engine.language,
                batch_size=8
            )
            
            # 使用WhisperX的对齐功能获取更精确的时间戳
            model_a, metadata = whisperx.load_align_model(language_code=asr_engine.language, device=asr_engine.device)
            aligned_result = whisperx.align(
                result["segments"],
                model_a,
                metadata,
                segment_path,
                asr_engine.device,
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
                        segment_words.extend(seg["words"])
            
            # 将说话人标识转换为可读格式
            readable_speaker = speaker
            if speaker == "SPEAKER_00":
                readable_speaker = "speakerA"
            elif speaker == "SPEAKER_01":
                readable_speaker = "speakerB"
            elif speaker.startswith("SPEAKER_"):
                # 提取数字部分并转换为字母
                num = int(speaker.split("_")[1])
                readable_speaker = f"speaker{chr(65 + (num % 26))}"
            
            # 添加到结果列表，增强结果数据结构
            segment_result = {
                "text": segment_text.strip(),
                "start_time": start_time,
                "end_time": end_time,
                "speaker": readable_speaker,
                "original_speaker": speaker,
                "confidence": result.get("detection_score", 1.0),  # 添加置信度
                "words": segment_words if segment_words else []  # 添加单词级别的时间戳
            }
            
            segment_results.append(segment_result)
            logger.info(f"识别结果: {segment_text.strip()}")
            
        except Exception as e:
            logger.error(f"识别片段失败: {str(e)}")
            # 如果识别失败，添加空结果
            segment_results.append({
                "text": "",
                "start_time": start_time,
                "end_time": end_time,
                "speaker": speaker,
                "original_speaker": speaker,
                "error": str(e)
            })
    
    # 按时间戳排序
    segment_results.sort(key=lambda x: x["start_time"])
    
    # 保存最终处理结果
    final_segments_path = os.path.join(session_dir, "segment_recognition_results.json")
    with open(final_segments_path, 'w', encoding='utf-8') as f:
        json.dump(segment_results, f, ensure_ascii=False, indent=2)
    logger.info(f"最终处理结果已保存至: {final_segments_path}")
    
    # 生成话者分离摘要文本
    summary_path = os.path.join(session_dir, "segment_recognition_summary.txt")
    with open(summary_path, 'w', encoding='utf-8') as f:
        for segment in segment_results:
            f.write(f"[{segment['speaker']}] 说话于 {segment['start_time']:.1f}s - {segment['end_time']:.1f}s: {segment['text']}\n")
    logger.info(f"话者分离摘要已保存至: {summary_path}")
    
    # 分组处理说话人，便于日志查看
    speaker_groups = {}
    for segment in segment_results:
        speaker = segment.get('speaker', 'UNKNOWN')
        speaker_groups.setdefault(speaker, []).append(segment)
    
    # 记录每个说话人的片段数量
    for speaker, speaker_segments in speaker_groups.items():
        logger.info(f"说话人 {speaker}: {len(speaker_segments)} 个片段")
    
    logger.info(f"处理完成，共识别出 {len(segment_results)} 个片段")
    return segment_results