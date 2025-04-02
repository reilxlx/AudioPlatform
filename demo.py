#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
from xinference.client import Client

def text_to_speech(text, reference_audio_file=None, reference_text=None, output_file=None):
    """使用FishSpeech-1.5模型将文本转换为语音
    
    Args:
        text (str): 要转换为语音的文本
        reference_audio_file (str, optional): 参考音频文件路径，用于声音克隆
        reference_text (str, optional): 参考音频中的文本内容
        output_file (str, optional): 输出MP3文件路径，若为None则自动生成
        
    Returns:
        str: 保存的MP3文件路径
    """
    try:
        # 初始化客户端
        client = Client("http://0.0.0.0:9997")
        
        # 获取FishSpeech-1.5模型
        model = client.get_model("FishSpeech-1.5")
        
        # 准备参数
        params = {}
        
        # 如果提供了参考音频文件
        if reference_audio_file and os.path.exists(reference_audio_file):
            print(f"使用参考音频文件: {reference_audio_file}")
            with open(reference_audio_file, "rb") as f:
                reference_audio = f.read()
            params["prompt_speech"] = reference_audio
            
            # 如果提供了参考文本
            if reference_text:
                print(f"使用参考文本: {reference_text}")
                params["prompt_text"] = reference_text
        
        # 生成语音
        print(f"正在生成文本的语音: {text}")
        speech_bytes = model.speech(text, **params)
        
        # 如果没有指定输出文件路径，则自动生成一个
        if output_file is None:
            # 创建输出目录
            os.makedirs("output", exist_ok=True)
            output_file = os.path.join("output", f"fishspeech_output_{int(time.time())}.mp3")
        
        # 保存为MP3文件
        with open(output_file, "wb") as f:
            f.write(speech_bytes)
        
        print(f"语音已成功生成并保存到: {output_file}")
        return output_file
    
    except Exception as e:
        print(f"生成语音时发生错误: {str(e)}")
        raise

def main():
    """主函数，演示如何使用FishSpeech-1.5模型进行文本转语音"""
    # 示例文本
    text = "在时光的流转中，我们如同匆匆过客，见证着生命的诞生与消逝，欢笑与泪水。我们在春天播下希望的种子，在夏日挥洒辛勤的汗水，在秋天收获成功的喜悦，在冬日反思沉淀。每一段经历，每一次感悟，都如同时光长河中的朵朵浪花，构成了我们丰富多彩的人生"
    
    # 参考音频文件路径（可选）
    # 注意：这个路径需要指向一个真实存在的音频文件
    reference_audio_file = "/Users/Downloads/xinference/demo.wav"  # 替换为您的参考音频文件路径
    
    # 参考音频中的文本内容（可选）
    # 注意：这个文本应该与参考音频文件中说的内容一致
    reference_text = "声纹识别是一种生物识别技术，其运作原理在于每个个体都拥有独特的声学特征，就像指纹或面部结构一样。该技术通过将捕获的声纹与存储的声纹模板数据库进行比较来识别或验证说话者的身份。"  # 替换为您的参考音频文本
    
    # 检查参考音频文件是否存在
    if not os.path.exists(reference_audio_file):
        print(f"警告: 参考音频文件 {reference_audio_file} 不存在，将使用默认音色。")
        reference_audio_file = None
        reference_text = None
    
    # 生成语音并保存为MP3文件
    output_file = text_to_speech(
        text,
        reference_audio_file=reference_audio_file,
        reference_text=reference_text
    )
    
    print(f"示例完成! 请查看生成的语音文件: {output_file}")

if __name__ == "__main__":
    main() 