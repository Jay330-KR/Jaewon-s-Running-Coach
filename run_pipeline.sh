#!/bin/bash
# Project 330 Running Coach - Pipeline Execution Script
# 이 스크립트는 백그라운드 웹훅 또는 로컬 스케줄러에 의해 기동되어 
# 스트라바 최신 러닝 로그를 연동하고 AI 코칭 대시보드(index.html)를 컴파일/갱신합니다.

echo "🎬 [Pipeline execution started]..."
python coach.py
echo "🏁 [Pipeline execution completed] index.html이 정상 갱신되었습니다."
