#!/usr/bin/env python3
"""
Academic Deep Research Demo - Enhanced Version with Paper Searcher
统一使用增强模式：Google Scholar优先、arXiv备用、会议筛选、引用数过滤、每轮充分性评估
"""

import json
import os
from pathlib import Path
from datetime import datetime
from deepseek_client import DeepSeekClient
from paper_searcher import EnhancedPaperSearcher, SearchFilters
from pdf_processor import EnhancedPDFProcessor
import time
from config import (
    OUTPUT_DIR, 
    MAX_ANALYSIS_PAPERS,
    NUM_SEARCH_QUERIES,
    PAPERS_PER_QUERY,
    USE_RETRY_ON_FAILURE,
    EXTRACT_FULL_PDF,
    ENABLE_CONCURRENT_ANALYSIS,
    MAX_CONCURRENT_ANALYSIS,
    SEARCH_DEPTH,
    MAX_PAPERS_PER_DEPTH,
    MIN_PAPERS_FOR_NEXT_DEPTH,
    DEPTH_SEARCH_QUERIES,
    PAPERS_PER_DEPTH_QUERY,
    ADEQUACY_EVALUATION_THRESHOLD,
    MIN_DEPTH_SEARCH_SCORE,
)

# 演示程序配置参数
DEFAULT_RESEARCH_TOPIC = "transformer attention mechanisms in neural networks"
ENABLE_DETAILED_ANALYSIS = True
GENERATE_RESEARCH_SUMMARY = True
SAVE_FULL_TEXT = True
SHOW_PROGRESS_DETAILS = True
MIN_PAPERS_FOR_CONTINUE = 3  # 继续搜索所需的最小论文数量

def print_banner():
    """打印程序横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                 深研星图-学术深度研究系统                         ║
║           Enhanced Academic Deep Research System             ║
║    Google Scholar + arXiv + Conference + Citation Filter     ║
║              + Adequacy Evaluation + Smart Stop              ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def get_research_topic():
    """获取研究主题"""
    print(f"🎯 请输入您的研究主题 (按回车使用默认主题):")
    print(f"   默认主题: {DEFAULT_RESEARCH_TOPIC}")
    
    research_topic = input("\n>>> ").strip()
    if not research_topic:
        research_topic = DEFAULT_RESEARCH_TOPIC
        print(f"使用默认主题: {research_topic}")
    
    return research_topic

def display_config():
    """显示当前配置"""
    if SHOW_PROGRESS_DETAILS:
        print("\n" + "="*60)
        print("📋模式配置:")
        print("="*60)
        print(f"  🔍 主要搜索源: Google Scholar")
        print(f"  📚 备用搜索源: arXiv")
        print(f"  🔄 搜索深度: {SEARCH_DEPTH} 轮")
        print(f"  📊 第一轮搜索查询数: {NUM_SEARCH_QUERIES}")
        print(f"  📄 每个查询的论文数: {PAPERS_PER_QUERY}")
        print(f"  📚 每轮最大处理论文数: {MAX_PAPERS_PER_DEPTH}")
        print(f"  🎯 深度搜索查询数: {DEPTH_SEARCH_QUERIES}")
        print(f"  📖 提取完整PDF: {'是' if EXTRACT_FULL_PDF else '否'}")
        print(f"  💾 保存完整文本: {'是' if SAVE_FULL_TEXT else '否'}")
        print(f"  🚀 并发分析: {'启用' if ENABLE_CONCURRENT_ANALYSIS else '禁用'}")
        if ENABLE_CONCURRENT_ANALYSIS:
            print(f"  ⚡ 最大并发数: {MAX_CONCURRENT_ANALYSIS}")
        print(f"  🎚️ 充分性评估阈值: {ADEQUACY_EVALUATION_THRESHOLD}")
        print(f"  📊 最小论文数要求: {MIN_PAPERS_FOR_CONTINUE} (每轮)")
        print(f"  🔄 每轮后进行充分性评估: 是")
        print(f"  🧠 智能终止: 启用")
        print("="*60)

def create_download_folder(research_topic: str):
    """创建下载文件夹"""
    sanitized_topic = research_topic.replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{sanitized_topic}_{timestamp}"
    result_dir = os.path.join(os.getcwd(), "downloads", folder_name)
    os.makedirs(result_dir, exist_ok=True)
    print(f"📁 已创建文件夹：{result_dir}")
    return result_dir

def process_papers_batch(papers_to_process, processor, download_dir, batch_name="论文"):
    """处理一批论文的通用函数"""
    print(f"\n📥 正在处理{batch_name}...")
    processed_papers = []
    
    for i, paper in enumerate(papers_to_process):
        if SHOW_PROGRESS_DETAILS:
            print(f"\n📄 正在处理{batch_name} {i+1}/{len(papers_to_process)}: {paper['title']}")
            if paper.get('citations', 0) > 0:
                print(f"    引用数: {paper['citations']}")
            print(f"    来源: {paper.get('source', 'unknown')}")
        else:
            print(f"📄 正在处理{batch_name} {i+1}/{len(papers_to_process)}...")
        
        processed_paper = processor.process_paper(paper, download_dir=download_dir)
        if processed_paper:
            processed_papers.append(processed_paper)
            if SHOW_PROGRESS_DETAILS:
                text_len = processed_paper.get('text_length', 0)
                chunks = len(processed_paper.get('text_chunks', []))
                print(f"✅ 处理成功 ({text_len:,} 字符, {chunks} 块)")
            else:
                print("✅ 处理成功")
        else:
            print("❌ 处理失败")
    
    return processed_papers

def analyze_papers_batch(processed_papers, ai_client, batch_name="论文"):
    """分析一批论文的通用函数"""
    analyses = []
    
    if ENABLE_DETAILED_ANALYSIS and processed_papers:
        papers_to_analyze = processed_papers[:MAX_ANALYSIS_PAPERS]
        
        if ENABLE_CONCURRENT_ANALYSIS and len(papers_to_analyze) > 1:
            print(f"\n🚀 正在使用并发模式分析{len(papers_to_analyze)}篇{batch_name}...")
            analyses = ai_client.analyze_papers_concurrently(papers_to_analyze)
        else:
            print(f"\n🧠 正在使用串行模式分析{len(papers_to_analyze)}篇{batch_name}...")
            for i, paper in enumerate(papers_to_analyze):
                if SHOW_PROGRESS_DETAILS:
                    print(f"  正在分析 {i+1}/{len(papers_to_analyze)}: {paper['title']}...")
                else:
                    print(f"  正在分析{batch_name} {i+1}/{len(papers_to_analyze)}...")
                
                try:
                    text_chunks = paper.get('text_chunks', [])
                    analysis = ai_client.analyze_paper_text(paper['title'], paper['abstract'], text_chunks)
                    
                    analyses.append({
                        'paper': paper['title'],
                        'paper_id': paper.get('arxiv_id', ''),
                        'analysis': analysis,
                        'text_length': paper.get('text_length', 0),
                        'citations': paper.get('citations', 0),
                        'source': paper.get('source', 'unknown')
                    })
                    if SHOW_PROGRESS_DETAILS:
                        print(f"  ✅ 分析完成")
                except Exception as e:
                    print(f"  ❌ 分析失败: {e}")
    
    return analyses

def perform_adequacy_evaluation_after_round(ai_client, all_analyses, research_topic, round_num):
    """每轮搜索后进行充分性评估"""
    print(f"\n🔍 第{round_num}轮充分性评估...")
    
    if not all_analyses:
        print("⚠️ 没有分析数据，无法进行充分性评估")
        return 0.0, "没有分析数据进行评估", []
    
    # 生成当前研究总结用于评估
    print(f"📝 正在生成第{round_num}轮研究总结用于充分性评估...")
    try:
        current_summary = ai_client.analyze_multiple_papers_summary(
            all_analyses, research_topic, depth_round=round_num
        )
        
        # 进行充分性评估
        print(f"🧠 正在使用高级模型评估研究资料充分性...")
        adequacy_score, evaluation_report, missing_areas = ai_client.evaluate_research_adequacy(
            current_summary, research_topic, len(all_analyses)
        )
        
        print(f"📊 第{round_num}轮充分性评估结果: {adequacy_score:.2f}/1.0")
        
        return adequacy_score, evaluation_report, missing_areas
        
    except Exception as e:
        print(f"❌ 充分性评估失败: {e}")
        return 0.0, f"评估失败: {e}", []

def should_continue_search(round_num, papers_found, adequacy_score):
    """判断是否应该继续搜索"""
    print(f"\n🤔 判断是否继续搜索...")
    print(f"   第{round_num}轮论文数量: {papers_found}")
    print(f"   充分性评分: {adequacy_score:.2f}")
    print(f"   充分性阈值: {ADEQUACY_EVALUATION_THRESHOLD}")
    print(f"   最小论文数要求: {MIN_PAPERS_FOR_CONTINUE}")
    
    # 条件1: 论文数量不足
    if papers_found < MIN_PAPERS_FOR_CONTINUE:
        print(f"✅ 继续搜索 - 论文数量不足({papers_found} < {MIN_PAPERS_FOR_CONTINUE})")
        return True, "论文数量不足"
    
    # 条件2: 充分性评分不足
    if adequacy_score < ADEQUACY_EVALUATION_THRESHOLD:
        print(f"✅ 继续搜索 - 充分性评分不足({adequacy_score:.2f} < {ADEQUACY_EVALUATION_THRESHOLD})")
        return True, "充分性评分不足"
    
    # 两个条件都满足，可以结束
    print(f"🛑 结束搜索 - 论文数量充足且充分性评分达标")
    return False, "论文数量和充分性都达标"

def perform_search_round(ai_client, searcher, research_topic, filters, round_num, previous_missing_areas=None, all_queries_used=None):
    """执行搜索轮次"""
    print(f"\n🔍 第{round_num}轮搜索 ...")
    
    if round_num == 1:
        print(f"🧠 正在使用DeepSeek生成{NUM_SEARCH_QUERIES}个初始搜索查询...")
        queries = ai_client.generate_search_queries(research_topic, num_queries=NUM_SEARCH_QUERIES)
    else:
        # 后续轮次：基于前一轮的评估结果生成深度搜索查询
        if previous_missing_areas:
            print(f"🎯 基于第{round_num-1}轮评估结果生成深度搜索查询...")
            print(f"   缺失领域: {', '.join(previous_missing_areas)}")
            
            # 生成针对缺失领域的查询
            queries = ai_client.generate_depth_search_queries(
                research_topic, previous_missing_areas, all_queries_used or [], num_queries=DEPTH_SEARCH_QUERIES
            )
            if not queries:  # 如果生成失败，使用通用深度查询
                queries = ai_client.generate_search_queries(f"advanced {research_topic}", num_queries=DEPTH_SEARCH_QUERIES)
        else:
            print(f"🎯 生成通用深度搜索查询...")
            queries = ai_client.generate_search_queries(f"advanced {research_topic}", num_queries=DEPTH_SEARCH_QUERIES)
    
    if SHOW_PROGRESS_DETAILS:
        print(f"第{round_num}轮查询:")
        for i, query in enumerate(queries, 1):
            print(f"  {i}. {query}")
    
    # 使用增强搜索器
    papers = searcher.search_multiple_queries_enhanced(queries, filters)
    
    if not papers:
        print(f"❌ 第{round_num}轮未找到任何论文!")
        return [], queries
    
    print(f"📚 第{round_num}轮找到{len(papers)}篇符合条件的论文")
    
    # 显示详细统计
    source_stats = {}
    citation_stats = []
    
    for paper in papers:
        source = paper.get('source', 'unknown')
        source_stats[source] = source_stats.get(source, 0) + 1
        if paper.get('citations', 0) > 0:
            citation_stats.append(paper['citations'])
    
    print(f"📊 来源分布: {', '.join([f'{k}: {v}篇' for k, v in source_stats.items()])}")
    
    if citation_stats:
        print(f"📈 引用数统计: 范围 {min(citation_stats)}-{max(citation_stats)}, 平均 {sum(citation_stats)/len(citation_stats):.1f}")
    
    return papers, queries

def main():
    print_banner()
    
    # 初始化组件
    print("🚀 正在初始搜索系统...")
    ai_client = DeepSeekClient()
    searcher = EnhancedPaperSearcher()
    processor = EnhancedPDFProcessor()
    
    print("✅ 学术搜索系统初始化完成")
    print("   - 主要搜索源: Google Scholar")
    print("   - 备用搜索源: arXiv")
    print("   - 智能过滤: 会议、引用数、时间范围")
    print("   - 充分性评估: 每轮自动评估")
    print("   - 智能终止: 基于评估结果决定")
    
    # 输出目录
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(exist_ok=True)
    
    # 获取研究主题
    research_topic = get_research_topic()
    # 开始计时
    start_time = time.time()

    print(f"\n📋 研究主题: {research_topic}")
    download_dir = create_download_folder(research_topic)
    
    # 获取搜索过滤器（增强模式）
    filters = searcher.get_user_search_preferences()
    
    # 显示配置
    display_config()
    
    # 初始化多轮搜索变量
    all_processed_papers = []
    all_analyses = []
    all_queries_used = []
    search_rounds_results = []
    final_adequacy_score = 0.0
    final_evaluation_report = ""
    
    try:
        # 多轮搜索循环
        for search_round in range(1, SEARCH_DEPTH + 1):
            print(f"\n{'='*80}")
            print(f"🔄 开始第 {search_round}/{SEARCH_DEPTH} 轮搜索")
            print(f"{'='*80}")
            
            # 获取上一轮的缺失领域（如果有）
            previous_missing_areas = None
            if len(search_rounds_results) > 0:
                previous_missing_areas = search_rounds_results[-1].get('missing_areas', [])
            
            # 执行搜索
            papers, queries = perform_search_round(
                ai_client, searcher, research_topic, filters, search_round, 
                previous_missing_areas, all_queries_used
            )
            
            # 记录使用的查询
            all_queries_used.extend(queries)
            
            if not papers:
                print(f"⚠️ 第{search_round}轮未找到论文，跳过此轮")
                
                # 即使没找到论文，也记录本轮结果
                round_result = {
                    'round': search_round,
                    'queries': queries,
                    'papers_found': 0,
                    'papers_processed': 0,
                    'papers_analyzed': 0,
                    'adequacy_score': 0.0,
                    'evaluation_report': "本轮未找到论文",
                    'missing_areas': [],
                    'should_continue': False,
                    'continue_reason': "未找到论文",
                    'source_distribution': {},
                    'cumulative_papers_analyzed': len(all_analyses),
                    'cumulative_papers_processed': len(all_processed_papers)
                }
                search_rounds_results.append(round_result)
                continue
            
            # 显示搜索结果摘要
            if SHOW_PROGRESS_DETAILS:
                searcher.display_search_results(papers, max_display=15)
            
            # 限制处理的论文数量
            papers_to_process = papers[:MAX_PAPERS_PER_DEPTH]
            print(f"📄 第{search_round}轮将处理{len(papers_to_process)}篇论文")
            
            # 处理论文
            processed_papers = process_papers_batch(
                papers_to_process, processor, download_dir, f"第{search_round}轮论文"
            )
            
            if not processed_papers:
                print(f"❌ 第{search_round}轮没有论文能够成功处理!")
                
                # 记录失败的轮次
                round_result = {
                    'round': search_round,
                    'queries': queries,
                    'papers_found': len(papers),
                    'papers_processed': 0,
                    'papers_analyzed': 0,
                    'adequacy_score': 0.0,
                    'evaluation_report': "论文处理失败",
                    'missing_areas': [],
                    'should_continue': False,
                    'continue_reason': "论文处理失败",
                    'source_distribution': {},
                    'cumulative_papers_analyzed': len(all_analyses),
                    'cumulative_papers_processed': len(all_processed_papers)
                }
                search_rounds_results.append(round_result)
                continue
            
            print(f"\n🎉 第{search_round}轮成功处理了{len(processed_papers)}篇论文!")
            
            # 分析论文
            analyses = analyze_papers_batch(processed_papers, ai_client, f"第{search_round}轮论文")
            
            # 累积结果
            all_processed_papers.extend(processed_papers)
            all_analyses.extend(analyses)
            
            # 每轮后立即进行充分性评估
            adequacy_score, evaluation_report, missing_areas = perform_adequacy_evaluation_after_round(
                ai_client, all_analyses, research_topic, search_round
            )
            
            # 判断是否应该继续搜索
            should_continue, continue_reason = should_continue_search(
                search_round, len(papers), adequacy_score
            )
            
            # 统计来源分布
            source_distribution = {}
            for paper in papers:
                source = paper.get('source', 'unknown')
                source_distribution[source] = source_distribution.get(source, 0) + 1
            
            # 记录本轮详细结果
            round_result = {
                'round': search_round,
                'queries': queries,
                'papers_found': len(papers),
                'papers_processed': len(processed_papers),
                'papers_analyzed': len(analyses),
                'adequacy_score': adequacy_score,
                'evaluation_report': evaluation_report,
                'missing_areas': missing_areas,
                'should_continue': should_continue,
                'continue_reason': continue_reason,
                'source_distribution': source_distribution,
                'cumulative_papers_analyzed': len(all_analyses),
                'cumulative_papers_processed': len(all_processed_papers)
            }
            search_rounds_results.append(round_result)
            
            print(f"\n📊 第{search_round}轮详细统计:")
            print(f"   找到论文: {len(papers)}")
            print(f"   成功处理: {len(processed_papers)}")
            print(f"   完成分析: {len(analyses)}")
            print(f"   来源分布: {source_distribution}")
            print(f"   充分性评分: {adequacy_score:.2f}/1.0")
            print(f"   累计已分析: {len(all_analyses)} 篇")
            
            # 显示引用数统计（如果有的话）
            if analyses:
                citations_data = [a.get('citations', 0) for a in analyses if a.get('citations', 0) > 0]
                if citations_data:
                    print(f"   引用数范围: {min(citations_data)} - {max(citations_data)}")
                    print(f"   平均引用数: {sum(citations_data) / len(citations_data):.1f}")
            
            # 根据充分性评估结果决定是否继续
            if not should_continue:
                print(f"\n🎯 第{search_round}轮后决定结束搜索")
                print(f"   原因: {continue_reason}")
                print(f"   最终充分性评分: {adequacy_score:.2f}")
                final_adequacy_score = adequacy_score
                final_evaluation_report = evaluation_report
                break
            elif search_round < SEARCH_DEPTH:
                print(f"\n➡️ 第{search_round}轮后决定继续搜索")
                print(f"   原因: {continue_reason}")
                if missing_areas:
                    print(f"   将重点关注: {', '.join(missing_areas[:3])}...")
                final_adequacy_score = adequacy_score
                final_evaluation_report = evaluation_report
            else:
                print(f"\n🔚 已达到最大搜索深度 {SEARCH_DEPTH}")
                final_adequacy_score = adequacy_score
                final_evaluation_report = evaluation_report
        
        # 生成最终研究总结
        final_research_summary = ""
        if GENERATE_RESEARCH_SUMMARY and all_analyses:
            print(f"\n📝 正在生成最终研究总结 (基于{len(all_analyses)}篇论文的分析)...")
            final_research_summary = ai_client.analyze_multiple_papers_summary(
                all_analyses, research_topic, depth_round=len(search_rounds_results)
            )
        
        # 保存结果
        results = {
            'research_topic': research_topic,
            'search_mode': 'enhanced',
            'search_source': 'google_scholar_arxiv',
            'search_depth': SEARCH_DEPTH,
            'actual_rounds_completed': len(search_rounds_results),
            'early_termination': len(search_rounds_results) < SEARCH_DEPTH,
            'termination_reason': search_rounds_results[-1].get('continue_reason', 'Unknown') if search_rounds_results else 'Unknown',
            'total_papers_found': sum(r['papers_found'] for r in search_rounds_results),
            'total_papers_processed': len(all_processed_papers),
            'total_papers_analyzed': len(all_analyses),
            'final_adequacy_score': final_adequacy_score,
            'final_evaluation_report': final_evaluation_report,
            'adequacy_threshold_used': ADEQUACY_EVALUATION_THRESHOLD,
            'search_rounds_results': search_rounds_results,  # 包含每轮的充分性评估
            'all_queries_used': all_queries_used,
            'filters_used': filters.__dict__ if filters else None,
            'adequacy_evaluation_timeline': [  # 充分性评估时间线
                {
                    'round': r['round'],
                    'adequacy_score': r['adequacy_score'],
                    'missing_areas': r['missing_areas'],
                    'cumulative_papers': r['cumulative_papers_analyzed'],
                    'should_continue': r['should_continue'],
                    'continue_reason': r['continue_reason']
                }
                for r in search_rounds_results
            ],
            'configuration': {
                'search_depth': SEARCH_DEPTH,
                'num_search_queries': NUM_SEARCH_QUERIES,
                'papers_per_query': PAPERS_PER_QUERY,
                'depth_search_queries': DEPTH_SEARCH_QUERIES,
                'papers_per_depth_query': PAPERS_PER_DEPTH_QUERY,
                'max_papers_per_depth': MAX_PAPERS_PER_DEPTH,
                'extract_full_pdf': EXTRACT_FULL_PDF,
                'max_analysis_papers': MAX_ANALYSIS_PAPERS,
                'concurrent_analysis_enabled': ENABLE_CONCURRENT_ANALYSIS,
                'max_concurrent_analysis': MAX_CONCURRENT_ANALYSIS if ENABLE_CONCURRENT_ANALYSIS else 0,
                'adequacy_evaluation_threshold': ADEQUACY_EVALUATION_THRESHOLD,
                'min_papers_for_continue': MIN_PAPERS_FOR_CONTINUE
            },
            'paper_analyses': all_analyses if ENABLE_DETAILED_ANALYSIS else [],
            'final_research_summary': final_research_summary
        }
        
        # 可选：保存完整文本
        if SAVE_FULL_TEXT:
            results['processed_papers'] = []
            for paper in all_processed_papers:
                paper_data = paper.copy()
                if not EXTRACT_FULL_PDF:
                    pass
                else:
                    if 'extracted_text' in paper_data and len(paper_data['extracted_text']) > 10000:
                        paper_data['extracted_text_preview'] = paper_data['extracted_text'][:5000] + "..."
                        paper_data['extracted_text_full'] = paper_data['extracted_text']
                
                results['processed_papers'].append(paper_data)
        
        # 保存到文件
        safe_topic = "".join(c for c in research_topic if c.isalnum() or c in (' ', '-', '_')).replace(' ', '_')
        output_file = output_dir / f"research_results_{safe_topic}_enhanced_depth{SEARCH_DEPTH}.json"
        
        print(f"\n💾 正在保存结果到 {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        # 显示最终结果
        print("\n" + "="*80)
        print("📊 学术深度研究结果总结")
        print("="*80)
        print(f"🎯 主题: {research_topic}")
        print(f"🔧 搜索模式: 默认为增强模式 (Google Scholar + arXiv + 智能过滤)")
        print(f"🔄 搜索深度: {SEARCH_DEPTH} 轮 (实际完成: {len(search_rounds_results)} 轮)")
        
        # 显示是否提前终止
        if len(search_rounds_results) < SEARCH_DEPTH:
            print(f"⏹️ 提前终止: 是 (原因: {results['termination_reason']})")
        else:
            print(f"⏹️ 提前终止: 否 (完成全部搜索轮次)")
        
        print(f"📝 使用的搜索查询总数: {len(all_queries_used)}")
        print(f"📚 找到的论文总数: {sum(r['papers_found'] for r in search_rounds_results)}")
        print(f"✅ 成功处理的论文: {len(all_processed_papers)}")
        print(f"🧠 已分析的论文: {len(all_analyses)}")
        print(f"📊 最终充分性评分: {final_adequacy_score:.2f}/1.0 (阈值: {ADEQUACY_EVALUATION_THRESHOLD})")
        
        # 显示总体来源分布
        total_source_stats = {}
        for round_result in search_rounds_results:
            for source, count in round_result.get('source_distribution', {}).items():
                total_source_stats[source] = total_source_stats.get(source, 0) + count
        
        if total_source_stats:
            print(f"\n📊 总体来源分布:")
            for source, count in total_source_stats.items():
                percentage = (count / sum(total_source_stats.values())) * 100
                print(f"   {source}: {count}篇 ({percentage:.1f}%)")
        
        if filters:
            print(f"\n🔧 使用的过滤条件:")
            if filters.conferences:
                print(f"   会议筛选: {', '.join(filters.conferences)}")
            if filters.exclude_conferences:
                print(f"   排除会议: {', '.join(filters.exclude_conferences)}")
            if filters.min_citations > 0:
                print(f"   最小引用数: {filters.min_citations}")
            if filters.max_citations:
                print(f"   最大引用数: {filters.max_citations}")
            if filters.start_date:
                print(f"   开始日期: {filters.start_date.strftime('%Y-%m-%d')}")
            if filters.end_date:
                print(f"   结束日期: {filters.end_date.strftime('%Y-%m-%d')}")
        
        # 显示引用数统计
        if all_analyses:
            citations_data = [a.get('citations', 0) for a in all_analyses if a.get('citations', 0) > 0]
            if citations_data:
                print(f"\n📊 引用数统计:")
                print(f"   有引用数的论文: {len(citations_data)}/{len(all_analyses)}")
                print(f"   引用数范围: {min(citations_data)} - {max(citations_data)}")
                print(f"   平均引用数: {sum(citations_data) / len(citations_data):.1f}")
                print(f"   高引用论文 (>100): {len([c for c in citations_data if c > 100])}")
        
        # 显示各轮充分性评估结果
        print(f"\n📈 各轮搜索与充分性评估统计:")
        for round_result in search_rounds_results:
            round_num = round_result['round']
            print(f"  第{round_num}轮:")
            print(f"    📚 论文: 找到{round_result['papers_found']}篇 | 处理{round_result['papers_processed']}篇 | 分析{round_result['papers_analyzed']}篇")
            print(f"    📊 充分性评分: {round_result['adequacy_score']:.2f}/1.0")
            print(f"    🤔 继续搜索: {'是' if round_result['should_continue'] else '否'} ({round_result['continue_reason']})")
            
            if round_result.get('missing_areas'):
                print(f"    🎯 缺失领域: {', '.join(round_result['missing_areas'][:3])}{'...' if len(round_result['missing_areas']) > 3 else ''}")
            
            source_dist = round_result.get('source_distribution', {})
            if source_dist:
                print(f"    🔍 来源分布: {', '.join([f'{k}:{v}' for k, v in source_dist.items()])}")
            print()
        
        # 显示充分性评估时间线
        print(f"📈 充分性评估时间线:")
        for eval_point in results['adequacy_evaluation_timeline']:
            print(f"  第{eval_point['round']}轮后: 评分 {eval_point['adequacy_score']:.2f} | 累计分析 {eval_point['cumulative_papers']}篇 | {'继续' if eval_point['should_continue'] else '结束'}")
        
        if final_research_summary:
            print(f"\n📝 最终研究总结:")
            print("-" * 60)
            print(final_research_summary)
        
        if final_evaluation_report:
            print(f"\n🔍 最终充分性评估报告:")
            print("-" * 60)
            print(final_evaluation_report)
        
        print(f"\n💾 完整结果已保存到: {output_file}")
        
        print("\n🎉 学术深度研究系统运行完成!")
        end_time = time.time()
        duration = end_time - start_time
        # 智能格式化
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = duration % 60

        if hours > 0:
            formatted = f"{hours}小时{minutes}分钟{seconds:.2f}秒"
        elif minutes > 0:
            formatted = f"{minutes}分钟{seconds:.2f}秒"
        else:
            formatted = f"{seconds:.2f}秒"

        print(f"✨ 智能搜索 + 过滤 + 每轮充分性评估 + 自动终止决策总用时: {formatted}")
            
        
    except Exception as e:
        print(f"\n❌ 研究过程中出现错误: {e}")
        if USE_RETRY_ON_FAILURE:
            print("🔄 您可以尝试重新运行程序。")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
