#!/usr/bin/env python3
"""
深研星图修复版快速演示脚本 - 使用多源搜索和模糊匹配
Research Constellation Fixed Quick Demo Script - Multi-source Search with Fuzzy Matching

修复过滤问题，使用增强的多源搜索器
Fixed filtering issues using enhanced multi-source searcher
"""

import os
import sys
from pathlib import Path

# 添加当前目录到Python路径
sys.path.append(str(Path(__file__).parent))

from deepseek_client import DeepSeekClient
from paper_searcher import EnhancedMultiSourcePaperSearcher, SearchFilters
from pdf_processor import EnhancedPDFProcessor
from datetime import datetime, timedelta

# 演示配置
DEMO_CONFIG = {
    'search_depth': 2,           # 搜索轮数：2轮
    'num_search_queries': 1,     # 初始查询数：1个
    'papers_per_query': 8,       # 每查询论文数：8篇 (增加以提高成功率)
    'depth_search_queries': 1,   # 深度搜索查询数：1个  
    'max_papers_per_depth': 6,   # 每轮最大处理论文数：6篇
    'adequacy_threshold': 0.6,   # 充分性阈值：0.6 (降低以便演示)
    'enable_pdf_download': False, # 关闭PDF下载以加快演示速度
    'demo_research_topic': "transformer attention mechanisms",  # 演示主题
    'enable_fuzzy_matching': True,    # 启用模糊匹配
    'similarity_threshold': 70        # 模糊匹配阈值
}

def create_fixed_demo_filters():
    """创建修复后的演示过滤器"""
    return SearchFilters(
        start_date=datetime.now() - timedelta(days=1825), # 最近5年 (进一步放宽)
        end_date=None,                                     # 不限制结束时间
        min_citations=0,                                   # 不限制引用数
        max_citations=None,                                # 不限制最大引用数
        conferences=None,                                  # 🔧 暂时移除会议筛选
        exclude_conferences=None,                          # 不排除会议
        categories=None,                                   # 不限制类别
        min_abstract_length=5,                             # 🔧 进一步降低摘要长度要求
        fuzzy_matching=DEMO_CONFIG['enable_fuzzy_matching'],  # 启用模糊匹配
        similarity_threshold=DEMO_CONFIG['similarity_threshold']  # 设置相似度阈值
    )

def demo_fixed_research():
    """
    修复版快速研究演示主函数
    Fixed quick research demo main function
    """
    print("🌟 深研星图修复版演示 (多源搜索 + 模糊匹配)")
    print("🌟 Research Constellation Fixed Demo (Multi-source + Fuzzy Matching)")
    print("=" * 70)
    
    # 初始化组件
    print("🔧 初始化增强型多源搜索系统...")
    print("🔧 Initializing enhanced multi-source search system...")
    
    try:
        ai_client = DeepSeekClient()
        searcher = EnhancedMultiSourcePaperSearcher()  # 使用新的多源搜索器
        processor = EnhancedPDFProcessor()
        print("✅ 组件初始化完成")
        print("✅ Components initialized successfully")
        print(f"   - 支持的搜索源: Google Scholar, {'scholarly, ' if searcher.scholarly_available else ''}DBLP, arXiv")
        print(f"   - Supported sources: Google Scholar, {'scholarly, ' if searcher.scholarly_available else ''}DBLP, arXiv")
        print(f"   - 模糊匹配: {'启用' if DEMO_CONFIG['enable_fuzzy_matching'] else '禁用'}")
        print(f"   - Fuzzy matching: {'Enabled' if DEMO_CONFIG['enable_fuzzy_matching'] else 'Disabled'}")
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        print(f"❌ Initialization failed: {e}")
        return
    
    # 研究主题
    research_topic = DEMO_CONFIG['demo_research_topic']
    print(f"\n🎯 演示研究主题: {research_topic}")
    print(f"🎯 Demo research topic: {research_topic}")
    
    # 创建下载目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    download_dir = Path("demo_downloads") / f"fixed_demo_{timestamp}"
    download_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 创建下载目录: {download_dir}")
    print(f"📁 Created download directory: {download_dir}")
    
    # 创建修复后的过滤器
    filters = create_fixed_demo_filters()
    print(f"🔍 应用修复后的过滤条件:")
    print(f"🔍 Applied fixed filter conditions:")
    print(f"   - 时间范围: 最近5年")
    print(f"   - Time range: Last 5 years")
    print(f"   - 会议筛选: None (暂时移除)")
    print(f"   - Conference filter: None (temporarily removed)")
    print(f"   - 最小摘要长度: 5字符")
    print(f"   - Minimum abstract length: 5 characters")
    print(f"   - 模糊匹配: 启用，阈值 {filters.similarity_threshold}")
    print(f"   - Fuzzy matching: Enabled, threshold {filters.similarity_threshold}")
    print(f"   - 多源搜索: Google Scholar → scholarly → DBLP → arXiv")
    print(f"   - Multi-source: Google Scholar → scholarly → DBLP → arXiv")
    
    all_analyses = []
    search_round = 1
    
    try:
        # 第一轮搜索
        print(f"\n{'='*60}")
        print(f"🔄 第 {search_round} 轮搜索 (多源增强)")
        print(f"🔄 Round {search_round} Search (Multi-source Enhanced)")
        print(f"{'='*60}")
        
        # 生成搜索查询
        print(f"🧠 生成搜索查询...")
        print(f"🧠 Generating search queries...")
        queries = ai_client.generate_search_queries(
            research_topic, 
            num_queries=DEMO_CONFIG['num_search_queries']
        )
        print(f"📝 生成的查询: {queries}")
        print(f"📝 Generated queries: {queries}")
        
        # 执行多源搜索
        print(f"🔍 执行多源论文搜索...")
        print(f"🔍 Executing multi-source paper search...")
        papers = searcher.search_multiple_queries_enhanced(queries, filters)
        
        if not papers:
            print("⚠️ 多源搜索未找到论文，这可能表明:")
            print("⚠️ Multi-source search found no papers, this might indicate:")
            print("   1. 网络连接问题")
            print("   1. Network connection issues")
            print("   2. 所有搜索源都暂时不可用")
            print("   2. All search sources temporarily unavailable")
            print("   3. 查询过于具体")
            print("   3. Query too specific")
            
            # 尝试更通用的查询作为fallback
            print("\n🔄 尝试更通用的查询作为fallback...")
            print("🔄 Trying more general query as fallback...")
            fallback_queries = ["transformer neural networks", "attention mechanism deep learning"]
            for fallback_query in fallback_queries:
                print(f"   尝试查询: {fallback_query}")
                print(f"   Trying query: {fallback_query}")
                papers = searcher.search_papers_multi_source(fallback_query, filters)
                if papers:
                    print(f"✅ Fallback查询成功，找到 {len(papers)} 篇论文")
                    print(f"✅ Fallback query successful, found {len(papers)} papers")
                    break
            
            if not papers:
                print("❌ 所有fallback查询都失败，演示结束")
                print("❌ All fallback queries failed, demo ended")
                return
        
        # 限制处理数量
        papers_to_process = papers[:DEMO_CONFIG['max_papers_per_depth']]
        print(f"📚 找到 {len(papers)} 篇论文，将处理 {len(papers_to_process)} 篇")
        print(f"📚 Found {len(papers)} papers, will process {len(papers_to_process)}")
        
        # 显示论文来源统计
        source_stats = {}
        for paper in papers:
            source = paper.get('source', 'unknown')
            source_stats[source] = source_stats.get(source, 0) + 1
        
        print(f"📊 论文来源分布:")
        print(f"📊 Paper source distribution:")
        for source, count in source_stats.items():
            print(f"   {source}: {count} 篇")
            print(f"   {source}: {count} papers")
        
        # 显示论文列表
        print(f"\n📋 将处理的论文:")
        print(f"📋 Papers to be processed:")
        for i, paper in enumerate(papers_to_process, 1):
            print(f"  {i}. {paper['title'][:60]}...")
            source_info = f"来源: {paper.get('source', 'unknown')}"
            citation_info = f"引用: {paper.get('citations', 0)}"
            venue_info = f"会议: {paper.get('venue', 'N/A')}" if paper.get('venue') else ""
            print(f"     {source_info} | {citation_info} {('| ' + venue_info) if venue_info else ''}")
        
        # 处理论文（简化版 - 主要使用摘要）
        processed_papers = []
        print(f"\n📥 开始处理论文 (快速模式)...")
        print(f"📥 Starting paper processing (quick mode)...")
        
        for i, paper in enumerate(papers_to_process, 1):
            print(f"📄 处理论文 {i}/{len(papers_to_process)}: {paper['title']}...")
            print(f"📄 Processing paper {i}/{len(papers_to_process)}: {paper['title']}...")
            
            if DEMO_CONFIG['enable_pdf_download']:
                # 尝试完整处理
                processed_paper = processor.process_paper(paper, str(download_dir))
                if processed_paper:
                    processed_papers.append(processed_paper)
                    print(f"✅ PDF处理成功")
                    print(f"✅ PDF processing successful")
                else:
                    # Fallback到摘要模式
                    paper['extracted_text'] = paper.get('abstract', '')
                    paper['text_chunks'] = [paper.get('abstract', '')]
                    paper['text_length'] = len(paper.get('abstract', ''))
                    processed_papers.append(paper)
                    print(f"📝 Fallback到摘要模式")
                    print(f"📝 Fallback to abstract mode")
            else:
                # 快速模式：仅使用摘要
                paper['extracted_text'] = paper.get('abstract', '')
                paper['text_chunks'] = [paper.get('abstract', '')]
                paper['text_length'] = len(paper.get('abstract', ''))
                processed_papers.append(paper)
                print(f"📝 快速模式 (摘要)")
                print(f"📝 Quick mode (abstract)")
        
        print(f"\n🎉 成功处理 {len(processed_papers)} 篇论文")
        print(f"🎉 Successfully processed {len(processed_papers)} papers")
        
        # AI分析论文
        print(f"\n🧠 开始AI分析...")
        print(f"🧠 Starting AI analysis...")
        
        for i, paper in enumerate(processed_papers, 1):
            print(f"  分析论文 {i}/{len(processed_papers)}: {paper['title']}...")
            print(f"  Analyzing paper {i}/{len(processed_papers)}: {paper['title'] }...")
            
            try:
                text_chunks = paper.get('text_chunks', [])
                analysis = ai_client.analyze_paper_text(
                    paper['title'], 
                    paper.get('abstract', ''), 
                    text_chunks
                )
                
                all_analyses.append({
                    'paper': paper['title'],
                    'analysis': analysis,
                    'citations': paper.get('citations', 0),
                    'source': paper.get('source', 'unknown'),
                    'venue': paper.get('venue', ''),
                    'published_str': paper.get('published_str', 'Unknown')
                })
                print(f"  ✅ 分析完成")
                print(f"  ✅ Analysis completed")
                
            except Exception as e:
                print(f"  ❌ 分析失败: {e}")
                print(f"  ❌ Analysis failed: {e}")
        
        # 生成研究总结
        if all_analyses:
            print(f"\n📝 生成研究总结...")
            print(f"📝 Generating research summary...")
            
            final_summary = ai_client.analyze_multiple_papers_summary(
                all_analyses, research_topic, depth_round=search_round
            )
            
            # 显示结果
            print(f"\n{'='*70}")
            print(f"🎯 深研星图修复版演示结果")
            print(f"🎯 Research Constellation Fixed Demo Results")
            print(f"{'='*70}")
            
            print(f"🔬 研究主题: {research_topic}")
            print(f"🔬 Research topic: {research_topic}")
            print(f"📊 搜索轮数: {search_round}")
            print(f"📊 Search rounds: {search_round}")
            print(f"📚 分析论文总数: {len(all_analyses)}")
            print(f"📚 Total papers analyzed: {len(all_analyses)}")
            print(f"🔍 使用的搜索源: {', '.join(source_stats.keys())}")
            print(f"🔍 Search sources used: {', '.join(source_stats.keys())}")
            print(f"🎯 模糊匹配阈值: {filters.similarity_threshold}")
            print(f"🎯 Fuzzy matching threshold: {filters.similarity_threshold}")
            
            # 显示各源论文统计
            analysis_source_stats = {}
            for analysis in all_analyses:
                source = analysis.get('source', 'unknown')
                analysis_source_stats[source] = analysis_source_stats.get(source, 0) + 1
            
            print(f"\n📊 分析论文来源分布:")
            print(f"📊 Analyzed papers source distribution:")
            for source, count in analysis_source_stats.items():
                print(f"   {source}: {count} 篇")
                print(f"   {source}: {count} papers")
            
            print(f"\n📝 研究总结:")
            print(f"📝 Research Summary:")
            print("-" * 60)
            print(final_summary)
            
            # 显示论文详情
            print(f"\n📚 分析的论文详情:")
            print(f"📚 Analyzed papers details:")
            print("-" * 60)
            for i, analysis in enumerate(all_analyses, 1):
                print(f"{i}. {analysis['paper']}")
                print(f"   来源: {analysis['source']} | 引用: {analysis['citations']} | 发表: {analysis['published_str']}")
                if analysis.get('venue'):
                    print(f"   会议/期刊: {analysis['venue']}")
                print(f"   分析摘要: {analysis['analysis'][:150]}...")
                print()
            
            # 保存结果
            result_file = download_dir / "fixed_demo_result.txt"
            with open(result_file, 'w', encoding='utf-8') as f:
                f.write(f"深研星图修复版演示结果\n")
                f.write(f"Research Constellation Fixed Demo Results\n")
                f.write(f"=" * 50 + "\n\n")
                f.write(f"研究主题: {research_topic}\n")
                f.write(f"搜索轮数: {search_round}\n")
                f.write(f"分析论文数: {len(all_analyses)}\n")
                f.write(f"使用的搜索源: {', '.join(source_stats.keys())}\n")
                f.write(f"模糊匹配阈值: {filters.similarity_threshold}\n\n")
                f.write(f"研究总结:\n{final_summary}\n\n")
                f.write(f"论文分析详情:\n")
                for i, analysis in enumerate(all_analyses, 1):
                    f.write(f"{i}. {analysis['paper']}\n")
                    f.write(f"来源: {analysis['source']} | 引用: {analysis['citations']}\n")
                    f.write(f"分析: {analysis['analysis'][:300]}...\n\n")
            
            print(f"\n💾 结果已保存到: {result_file}")
            print(f"💾 Results saved to: {result_file}")
            
        else:
            print("❌ 没有成功分析的论文")
            print("❌ No successfully analyzed papers")
    
    except Exception as e:
        print(f"❌ 演示过程中出现错误: {e}")
        print(f"❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n🎉 深研星图修复版演示完成！")
    print(f"🎉 Research Constellation fixed demo completed!")
    print(f"🌟 特色功能:")
    print(f"🌟 Featured capabilities:")
    print(f"   ✅ 多源搜索: 自动fallback到不同数据源")
    print(f"   ✅ Multi-source search: Auto-fallback to different data sources")
    print(f"   ✅ 模糊匹配: 容忍细节误差，提高匹配成功率")
    print(f"   ✅ Fuzzy matching: Tolerates detail errors, improves matching success rate")
    print(f"   ✅ 智能去重: 基于内容相似度去除重复论文")
    print(f"   ✅ Smart deduplication: Remove duplicate papers based on content similarity")

if __name__ == "__main__":
    demo_fixed_research()