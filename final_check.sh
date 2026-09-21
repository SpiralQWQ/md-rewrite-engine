#!/bin/bash
# 全 14 章终检：gate_check 逐章跑，输出 PASS/FAIL 汇总
cd "$(dirname "$0")"   # repo root (script lives at top level)
pairs=(
  "第1章_初识Scrapy_笔记.md|第1章_clean_only.md"
  "第2章_编写Spider_笔记.md|第2章_编写Spider_clean.md"
  "第3章_使用Selector_笔记.md|第3章_clean.md"
  "第4章_使用Item_笔记.md|第4章_clean.md"
  "第5章_使用ItemPipeline_笔记.md|第5章_clean.md"
  "第6章_使用LinkExtractor_笔记.md|第6章_clean_only.md"
  "第7章_使用Exporter_笔记.md|第7章_clean_only.md"
  "第8章_项目练习_笔记.md|第8章_clean_only.md"
  "第9章_下载文件_笔记.md|第9章_clean_only.md"
  "第10章_模拟登录_笔记.md|第10章_clean_only.md"
  "第11章_爬取动态页面_笔记.md|第11章_clean_only.md"
  "第12章_存入数据库_笔记.md|第12章_clean_only.md"
  "第13章_使用HTTP代理_笔记.md|第13章_clean_only.md"
  "第14章_分布式爬取_笔记.md|第14章_clean_only.md"
)
pass=0; fail=0
for pair in "${pairs[@]}"; do
  note="${pair%%|*}"; src="${pair##*|}"
  result=$(PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m scripts.gate_check "temp/$note" --src "temp/$src" 2>&1 | grep "判定")
  if echo "$result" | grep -q "PASS"; then
    echo "✅ $note  $result"
    pass=$((pass+1))
  else
    echo "❌ $note  $result"
    fail=$((fail+1))
  fi
done
echo "================================"
echo "总计: PASS=$pass FAIL=$fail"