import os
import re

if os.path.exists("README.md"):
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()

    # 차트 URL 인코딩 문제 해결 및 마크다운 문법을 HTML로 정밀 변환
    content = content.replace("---", "<hr>")
    content = re.sub(r'# 🏃‍♂️ (.*)', r'<h1>🏃‍♂️ \1</h1>', content)
    content = re.sub(r'## 📈 (.*)', r'<h2>📈 \1</h2>', content)
    content = re.sub(r'## ⏱️ (.*)', r'<h2>⏱️ \1</h2>', content)
    content = re.sub(r'## 📊 (.*)', r'<h2>📊 \1</h2>', content)
    content = re.sub(r'## 🛠️ (.*)', r'<h2>🛠️ \1</h2>', content)
    content = re.sub(r'### 📋 (.*)', r'<h3>📋 \1</h3>', content)
    content = re.sub(r'### 🔮 (.*)', r'<h3>🔮 \1</h3>', content)
    content = re.sub(r'### 🎯 (.*)', r'<h3>🎯 \1</h3>', content)
    content = re.sub(r'### 🔲 (.*)', r'<h3>🔲 \1</h3>', content)
    
    # 인용문 변환
    content = re.sub(r'> \*\*(.*?)\*\*(.*)', r'<blockquote><strong>\1</strong>\2</blockquote>', content)
    content = re.sub(r'> (.*)', r'<blockquote>\1</blockquote>', content)
    
    # 이미지 차트 태그 변환
    content = re.sub(r'!\[.*?\]\((.*?)\)', r'<div class="chart-container"><img src="\1" /></div>', content)
    
    # 리스트 및 강조 변환
    content = re.sub(r'\* \*\*(.*?)\*\* (.*)', r'<li><strong>\1</strong> \2</li>', content)
    content = re.sub(r'- \[\s\] (.*?) -> (.*)', r'<li class="todo-item"><input type="checkbox"> <span><strong>\1</strong><br><small>\2</small></span></li>', content)
    content = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', content)

    # 전체 홈페이지 디자인 뼈대 구성 (다크 스포티 테마)
    html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project 330 Running Dashboard</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #121212; color: #e0e0e0; margin: 0; padding: 16px; line-height: 1.6; }}
        .container {{ max-width: 600px; margin: 0 auto; background: #1e1e1e; padding: 20px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }}
        h1 {{ color: #FC4C02; text-align: center; font-size: 24px; margin-bottom: 5px; }}
        h2 {{ color: #ffffff; border-bottom: 1px solid #333; padding-bottom: 8px; font-size: 18px; margin-top: 25px; }}
        h3 {{ color: #FC4C02; font-size: 15px; margin-top: 15px; }}
        blockquote {{ background: #2a2a2a; border-left: 4px solid #FC4C02; margin: 15px 0; padding: 12px; border-radius: 4px; font-style: italic; color: #ccc; }}
        hr {{ border: 0; height: 1px; background: #333; margin: 20px 0; }}
        ul {{ padding-left: 20px; }}
        li {{ margin-bottom: 8px; list-style-type: none; }}
        .chart-container {{ text-align: center; margin: 15px 0; background: #252525; padding: 10px; border-radius: 12px; }}
        .chart-container img {{ max-width: 100%; height: auto; }}
        .todo-item {{ display: flex; align-items: flex-start; margin-bottom: 12px; background: #252525; padding: 10px; border-radius: 8px; }}
        .todo-item input {{ margin-top: 4px; margin-right: 10px; transform: scale(1.2); accent-color: #FC4C02; }}
        .todo-item small {{ color: #888; }}
        footer {{ text-align: center; font-size: 11px; color: #555; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        {content}
        <footer>Automated via Strava API & QuickChart API</footer>
    </div>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_template)
