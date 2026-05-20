#!/bin/bash
python coach.py

# README.md 파일이 존재하면 HTML 대문 파일로 변환/복사
if [ -f "README.md" ]; then
  echo "<html><head><meta charset='utf-8'><title>Project 330 Running Coach</title><style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;line-height:1.6;max-width:800px;margin:0 auto;padding:20px;background:#f9f9f9;color:#333;}pre{background:#fff;padding:15px;border-radius:8px;border:1px solid #ddd;overflow-x:auto;}img{max-width:100%;height:auto;}</style></head><body>" > index.html
  
  # 마크다운의 주황색 바 차트나 텍스트를 웹 화면에 맞게 최소한의 안전 변환하여 주입
  cat README.md >> index.html
  
  echo "</body></html>" >> index.html
fi
