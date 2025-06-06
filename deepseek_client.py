import requests
import time
import re
import threading
import json
from typing import List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import (
    API_KEYS, 
    API_KEYS_2,
    API_ENDPOINT, 
    MODEL_NAME,
    SUMMARY_MODEL_NAME,
    SUMMARY_API_ENDPOINT,
    MAX_TOKENS_PER_REQUEST,
    SUMMARY_MAX_TOKENS_PER_REQUEST,
    MAX_CONTENT_LENGTH,
    API_TIMEOUT,
    SUMMARY_API_TIMEOUT,
    API_RETRY_COUNT,
    SUMMARY_API_RETRY_COUNT,
    SUMMARY_TEMPERATURE,
    MAX_INPUT_TOKENS,
    ENABLE_CONCURRENT_ANALYSIS,
    MAX_CONCURRENT_ANALYSIS,
    CONCURRENT_BATCH_SIZE,
    ANALYSIS_RATE_LIMIT_DELAY,
    MAX_ANAYLISE_PAPERS,
    SINGLE_ANAYLISE_LENTH,
    MAX_ANAYLISE_OUTPUT_LENGTH,
    ADEQUACY_EVALUATION_THRESHOLD,
    MIN_DEPTH_SEARCH_SCORE,
    MAX_NEW_KEYWORDS_PER_DEPTH,
)

class DeepSeekClient:
    def __init__(self):
        self.api_keys = API_KEYS
        self.summary_api_keys = API_KEYS_2 if API_KEYS_2 else API_KEYS  # 如果没有专用密钥，使用普通密钥
        self.endpoint = API_ENDPOINT
        self.summary_endpoint = SUMMARY_API_ENDPOINT
        self.model = MODEL_NAME
        self.summary_model = SUMMARY_MODEL_NAME
        self.current_key_index = 0
        self.current_summary_key_index = 0
        self.key_lock = threading.Lock()  # 线程安全的密钥轮换
        self.summary_key_lock = threading.Lock()  # 总结API密钥锁
        
        # 从配置文件读取设置
        self.max_tokens_per_request = MAX_TOKENS_PER_REQUEST
        self.max_content_length = MAX_CONTENT_LENGTH
        self.api_timeout = API_TIMEOUT
        self.max_retries = API_RETRY_COUNT
        
        print(f"🔧 DeepSeek客户端初始化完成")
        print(f"   - 可用API密钥数量: {len(self.api_keys)}")
        print(f"   - 总结专用密钥数量: {len(self.summary_api_keys)}")
        print(f"   - 普通模型: {self.model}")
        print(f"   - 总结模型: {self.summary_model}")
        print(f"   - 最大token数: {self.max_tokens_per_request}")
        print(f"   - 并发分析: {'启用' if ENABLE_CONCURRENT_ANALYSIS else '禁用'}")
        if ENABLE_CONCURRENT_ANALYSIS:
            print(f"   - 最大并发数: {MAX_CONCURRENT_ANALYSIS}")
    
    def _get_next_api_key(self):
        """线程安全的API密钥轮换"""
        with self.key_lock:
            key = self.api_keys[self.current_key_index]
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            return key
    
    def _get_next_summary_api_key(self):
        """线程安全的总结API密钥轮换"""
        with self.summary_key_lock:
            key = self.summary_api_keys[self.current_summary_key_index]
            self.current_summary_key_index = (self.current_summary_key_index + 1) % len(self.summary_api_keys)
            return key
    
    def _estimate_tokens(self, text: str) -> int:
        """估算文本的token数量"""
        # 粗略估算：英文约4字符=1token，中文约1.5字符=1token
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_chars = len(text) - chinese_chars
        estimated_tokens = (english_chars // 4) + (chinese_chars * 2 // 3)
        return estimated_tokens
    
    def _truncate_content_if_needed(self, content: str, max_tokens: int = None) -> str:
        """如果内容太长，智能截断"""
        if max_tokens is None:
            max_tokens = MAX_INPUT_TOKENS  # 留一半给回复
        
        estimated_tokens = self._estimate_tokens(content)
        
        if estimated_tokens <= max_tokens:
            return content
        
        # 需要截断
        target_length = int(len(content) * (max_tokens / estimated_tokens) * 0.9)  # 保守估计
        
        if target_length < len(content):
            # 尝试在句号处截断
            truncated = content[:target_length]
            last_period = truncated.rfind('.')
            
            if last_period > target_length // 2:
                truncated = truncated[:last_period + 1]
            
            # 添加截断提示
            truncated += f"\n\n[由于长度限制，内容已从{len(content)}字符截断至{len(truncated)}字符]"
            
            print(f"⚠️ 内容已从{len(content)}字符截断至{len(truncated)}字符")
            return truncated
        
        return content
    
    def ask(self, prompt: str, max_retries: int = None, temperature: float = 0.3, use_summary_api: bool = False) -> str:
        """发送请求到DeepSeek，支持选择使用总结API"""
        if max_retries is None:
            max_retries = SUMMARY_API_RETRY_COUNT if use_summary_api else self.max_retries
        
        # 根据是否使用总结API选择配置
        if use_summary_api:
            api_key = self._get_next_summary_api_key()
            endpoint = self.summary_endpoint
            model = self.summary_model
            max_tokens = SUMMARY_MAX_TOKENS_PER_REQUEST
            timeout = SUMMARY_API_TIMEOUT
            max_input_tokens = int(MAX_INPUT_TOKENS * 1.5)  # 总结API可以处理更多token
        else:
            api_key = self._get_next_api_key()
            endpoint = self.endpoint
            model = self.model
            max_tokens = self.max_tokens_per_request
            timeout = self.api_timeout
            max_input_tokens = MAX_INPUT_TOKENS
        
        # 估算token数量，如果超出限制则截断
        estimated_tokens = self._estimate_tokens(prompt)
        if estimated_tokens > max_input_tokens:
            print(f"⚠️ 输入内容token数量 ({estimated_tokens}) 超过限制 ({max_input_tokens})，正在截断...")
            prompt = self._truncate_content_if_needed(prompt, max_tokens=max_input_tokens)
        
        # 检查并截断过长的内容（基于字符长度限制）
        if len(prompt) > self.max_content_length:
            prompt = self._truncate_content_if_needed(prompt)
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "max_tokens": min(max_tokens, 16384),
            "temperature": temperature,
        }
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    endpoint, 
                    json=payload, 
                    headers=headers, 
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result['choices'][0]['message']['content'].strip()
                elif response.status_code == 429:
                    # Rate limit exceeded
                    print(f"⚠️ API调用频率限制，切换密钥...")
                    if use_summary_api:
                        api_key = self._get_next_summary_api_key()
                    else:
                        api_key = self._get_next_api_key()
                    headers["Authorization"] = f"Bearer {api_key}"
                    time.sleep(2)
                    continue
                else:
                    print(f"API错误: {response.status_code} - {response.text}")
                    
            except Exception as e:
                print(f"请求失败 (尝试 {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        
        return "错误: 无法获取响应"
    
    def generate_search_queries(self, research_topic: str, num_queries: int = 3) -> List[str]:
        """生成arXiv兼容的搜索查询"""
        
        prompt = f"""
你需要为研究主题生成{num_queries}个纯净的英文搜索查询，用于在arXiv上搜索论文。

研究主题: "{research_topic}"

要求:
1. 只返回纯英文关键词组合，每行一个查询
2. 不要包含任何解释、描述或中文
3. 不要使用特殊符号如**、()、引号等
4. 不要使用复杂语法如PA:、TS:、PUBYEAR等
5. 保持简洁，每个查询2-4个关键词

示例格式（直接返回查询，不要编号）:
transformer attention mechanism
neural networks attention
self attention transformer

现在为主题"{research_topic}"生成{num_queries}个查询:
"""
        
        response = self.ask(prompt)
        
        # 解析并清理查询
        queries = self._parse_and_clean_queries_improved(response, num_queries)
        
        # 如果生成的查询不够，添加fallback查询
        if len(queries) < num_queries:
            print(f"⚠️ 生成的查询不足，添加fallback查询...")
            fallback_queries = self._generate_fallback_queries(research_topic)
            queries.extend(fallback_queries)
        
        return queries[:num_queries]
    
    def _parse_and_clean_queries_improved(self, response: str, num_queries: int) -> List[str]:
        """改进的查询解析和清理"""
        queries = []
        
        # 分行处理
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # 跳过空行、标题行、说明行
            if not line:
                continue
            if any(keyword in line.lower() for keyword in ['要求', '示例', '格式', '现在', '主题', '生成', '查询', 'requirement', 'example']):
                continue
            
            # 提取可能的查询
            potential_query = self._extract_query_from_line(line)
            
            if potential_query:
                cleaned_query = self._clean_query_aggressive(potential_query)
                
                if self._is_valid_query(cleaned_query):
                    queries.append(cleaned_query)
                    if len(queries) >= num_queries:
                        break
        
        return queries
    
    def _extract_query_from_line(self, line: str) -> str:
        """从一行文本中提取查询"""
        # 移除常见的编号和前缀
        line = re.sub(r'^\d+[\.\)]\s*', '', line)  # 移除 "1. " 或 "1) "
        line = re.sub(r'^[-*•]\s*', '', line)      # 移除 "- " 或 "* "
        
        # 移除 markdown 格式
        line = re.sub(r'\*\*(.*?)\*\*', r'\1', line)  # 移除 **text**
        line = re.sub(r'\*(.*?)\*', r'\1', line)      # 移除 *text*
        
        # 移除引号
        line = re.sub(r'["""\'\'`]', '', line)
        
        # 如果包含中文解释，只取英文部分
        chinese_match = re.search(r'[\u4e00-\u9fff]', line)
        if chinese_match:
            line = line[:chinese_match.start()]
        
        # 移除特殊符号和多余空格
        line = re.sub(r'[^\w\s]', ' ', line)
        line = re.sub(r'\s+', ' ', line)
        
        return line.strip()
    
    def _clean_query_aggressive(self, query: str) -> str:
        """积极的查询清理"""
        if not query:
            return ""
        
        # 移除所有非英文字母、数字、空格的字符
        query = re.sub(r'[^\w\s]', ' ', query)
        
        # 移除中文字符
        query = re.sub(r'[\u4e00-\u9fff]', ' ', query)
        
        # 移除数字（通常不需要）
        query = re.sub(r'\b\d+\b', ' ', query)
        
        # 移除单个字母（除了常见缩写）
        words = query.split()
        valid_words = []
        for word in words:
            word = word.strip().lower()
            if len(word) >= 2 or word in ['ai', 'ml', 'dl', 'cv', 'nlp', 'db']:
                valid_words.append(word)
        
        # 重新组合
        query = ' '.join(valid_words)
        
        # 移除多余空格
        query = re.sub(r'\s+', ' ', query).strip()
        
        return query
    
    def _is_valid_query(self, query: str) -> bool:
        """验证查询是否有效"""
        if not query or len(query) < 3:
            return False
        
        # 检查是否包含足够的英文字母
        english_chars = len(re.findall(r'[a-zA-Z]', query))
        if english_chars < 3:
            return False
        
        # 检查单词数量（至少1个，最多8个）
        words = query.split()
        if len(words) < 1 or len(words) > 8:
            return False
        
        # 检查是否包含无效内容
        invalid_patterns = ['要求', '示例', '格式', '主题', '查询', 'example', 'query', 'search']
        for pattern in invalid_patterns:
            if pattern.lower() in query.lower():
                return False
        
        return True
    
    def _generate_fallback_queries(self, research_topic: str) -> List[str]:
        """生成fallback查询"""
        print(f"📝 生成fallback查询，主题: {research_topic}")
        
        keywords = self._extract_keywords_from_topic(research_topic)
        
        fallback_queries = []
        
        if keywords:
            # 生成简单的关键词组合
            if len(keywords) >= 2:
                fallback_queries.append(' '.join(keywords[:2]))
            if len(keywords) >= 3:
                fallback_queries.append(' '.join(keywords[:3]))
            
            # 单个重要关键词
            for keyword in keywords[:2]:
                if len(keyword) > 4:
                    fallback_queries.append(keyword)
        
        # 添加一些通用的备用查询
        if 'transformer' in research_topic.lower():
            fallback_queries.extend([
                'transformer attention',
                'attention mechanism',
                'self attention'
            ])
        elif 'neural' in research_topic.lower():
            fallback_queries.extend([
                'neural networks',
                'deep learning',
                'machine learning'
            ])
        else:
            # 通用查询
            fallback_queries.extend([
                'deep learning',
                'machine learning',
                'artificial intelligence'
            ])
        
        print(f"📝 生成的fallback查询: {fallback_queries}")
        return fallback_queries
    
    def _extract_keywords_from_topic(self, topic: str) -> List[str]:
        """从研究主题中提取关键词"""
        # 移除中文和特殊字符，提取英文关键词
        english_text = re.sub(r'[^\w\s]', ' ', topic)
        english_text = re.sub(r'[\u4e00-\u9fff]', ' ', english_text)  # 移除中文
        
        # 分词并过滤
        words = english_text.split()
        
        # 过滤停用词和短词
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        keywords = [word.lower() for word in words 
                   if word.lower() not in stop_words and len(word) > 2]
        
        return keywords[:5]
    
    def analyze_paper_text(self, title: str, abstract: str, text_chunks: List[str] = None) -> str:
        """
        分析单篇论文，使用累积式分析处理多个chunks
        
        Args:
            title: 论文标题
            abstract: 论文摘要
            text_chunks: PDF处理器提供的文本块列表
        
        Returns:
            分析结果
        """
        
        # 如果没有提供chunks或只有一个chunk，直接分析
        if not text_chunks or len(text_chunks) == 1:
            content_to_analyze = text_chunks[0] if text_chunks else abstract
            content_type = "完整文本" if text_chunks else "摘要"
            return self._analyze_single_content(title, content_to_analyze, content_type)
        
        # 多个chunks的累积式分析
        print(f"📚 使用累积式分析处理{len(text_chunks)}个文本块...")
        return self._analyze_with_cumulative_approach(title, abstract, text_chunks)
    
    def _analyze_single_content(self, title: str, content: str, content_type: str) -> str:
        """分析单个内容块"""
        prompt = f"""
请基于{content_type}分析这篇研究论文并提供结构化总结:

标题: {title}

内容:
{content}

请提供:
1. 主要贡献 (1-2句话)
2. 技术方法 (3-4句话，包含具体方法/算法)
3. 关键结果/发现 (2-3句话)
4. 对该领域的意义 (2句话)
5. 局限性或未来工作 (1-2句话)
6. 关键技术词汇 (5-7个技术术语)

请保持简洁但全面，重点关注技术细节和研究影响。
"""
        
        return self.ask(prompt, temperature=0.2)
    
    def _analyze_with_cumulative_approach(self, title: str, abstract: str, text_chunks: List[str]) -> str:
        """
        使用累积式方法分析多个文本块
        
        分析流程: chunk1 -> a1, a1+chunk2 -> a2, a2+chunk3 -> a3, ...
        """
        
        # 初始分析：基于摘要和第一个chunk
        print(f"  📝 分析第1个块...")
        
        first_chunk_prompt = f"""
请分析这篇研究论文的开始部分并提供初步总结:

标题: {title}
摘要: {abstract}

论文开始部分:
{text_chunks[0]}

请提供简洁的初步分析:
1. 主要研究目标和贡献
2. 使用的技术方法
3. 初步发现的关键信息
4. 重要的技术术语

这是多部分分析的第1部分，请保持分析简洁，为后续部分留出空间。
"""
        
        current_analysis = self.ask(first_chunk_prompt, temperature=0.2)
        
        # 逐步累积分析后续chunks
        for i, chunk in enumerate(text_chunks[1:], 2):
            print(f"  📝 分析第{i}个块...")
            
            cumulative_prompt = f"""
继续分析这篇研究论文，请基于之前的分析结果和新的内容部分更新总结:

论文标题: {title}

之前的分析结果:
{current_analysis}

新的内容部分 (第{i}部分):
{chunk}

请更新和完善分析，重点关注:
1. 新内容中的关键信息
2. 与之前分析的关联和补充
3. 更完整的技术方法描述
4. 新发现的结果或发现
5. 补充的技术术语

请提供更新后的完整分析，保持结构清晰。这是第{i}/{len(text_chunks)}部分。
"""
            
            try:
                current_analysis = self.ask(cumulative_prompt, temperature=0.2)
                time.sleep(0.3)  # 避免请求过快
            except Exception as e:
                print(f"    ⚠️ 第{i}块分析失败: {e}")
                # 如果某个块分析失败，继续使用之前的分析结果
                break
        
        # 最终整理分析结果
        print(f"  🔄 整理最终分析结果...")
        
        final_prompt = f"""
基于对论文各部分的累积分析，请提供最终的结构化总结:

论文标题: {title}

累积分析结果:
{current_analysis}

请提供最终的结构化总结:
1. 主要贡献 (1-2句话)
2. 技术方法 (3-4句话，包含具体方法/算法)
3. 关键结果/发现 (2-3句话)
4. 对该领域的意义 (2句话)
5. 局限性或未来工作 (1-2句话)
6. 关键技术词汇 (5-7个技术术语)

请综合所有分析内容，提供完整而连贯的最终总结。
"""
        
        try:
            final_analysis = self.ask(final_prompt, temperature=0.2)
            print(f"  ✅ 累积式分析完成")
            return final_analysis
        except Exception as e:
            print(f"  ❌ 最终分析失败: {e}")
            # 如果最终分析失败，返回最后的累积结果
            return current_analysis + "\n\n[注: 最终整理步骤失败，使用累积分析结果]"
    
    def analyze_papers_concurrently(self, papers: List[Dict]) -> List[Dict]:
        """并发分析多篇论文"""
        if not ENABLE_CONCURRENT_ANALYSIS or len(papers) <= 1:
            # 如果禁用并发或论文数量太少，使用串行处理
            return self._analyze_papers_sequentially(papers)
        
        print(f"🚀 开始并发分析{len(papers)}篇论文...")
        print(f"   - 最大并发数: {MAX_CONCURRENT_ANALYSIS}")
        print(f"   - 批处理大小: {CONCURRENT_BATCH_SIZE}")
        
        analyses = []
        total_papers = len(papers)
        
        # 分批处理论文
        for batch_start in range(0, total_papers, CONCURRENT_BATCH_SIZE):
            batch_end = min(batch_start + CONCURRENT_BATCH_SIZE, total_papers)
            batch_papers = papers[batch_start:batch_end]
            
            print(f"📊 处理批次 {batch_start//CONCURRENT_BATCH_SIZE + 1}: 论文 {batch_start+1}-{batch_end}")
            
            batch_analyses = self._analyze_batch_concurrently(batch_papers, batch_start)
            analyses.extend(batch_analyses)
            
            # 批次之间添加延迟
            if batch_end < total_papers:
                time.sleep(ANALYSIS_RATE_LIMIT_DELAY * 2)
        
        print(f"✅ 并发分析完成，成功分析{len(analyses)}篇论文")
        return analyses
    
    def _analyze_batch_concurrently(self, papers: List[Dict], batch_offset: int = 0) -> List[Dict]:
        """并发分析一批论文"""
        analyses = []
        max_workers = min(MAX_CONCURRENT_ANALYSIS, len(self.api_keys), len(papers))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有分析任务
            future_to_paper = {}
            for i, paper in enumerate(papers):
                future = executor.submit(self._analyze_single_paper_with_retry, paper, batch_offset + i + 1)
                future_to_paper[future] = paper
            
            # 收集结果
            for future in as_completed(future_to_paper):
                paper = future_to_paper[future]
                try:
                    analysis = future.result()
                    if analysis:
                        analyses.append(analysis)
                        print(f"  ✅ 完成分析: {paper['title']}")
                    else:
                        print(f"  ❌ 分析失败: {paper['title']}")
                except Exception as e:
                    print(f"  ❌ 分析异常: {paper['title']} - {e}")
        
        return analyses
    
    def _analyze_single_paper_with_retry(self, paper: Dict, paper_index: int) -> Dict:
        """分析单篇论文并包含重试机制"""
        try:
            # 添加小的随机延迟以避免同时请求
            time.sleep(ANALYSIS_RATE_LIMIT_DELAY * (paper_index % 4))
            
            # 使用新的分析方法
            text_chunks = paper.get('text_chunks', [])
            analysis = self.analyze_paper_text(paper['title'], paper['abstract'], text_chunks)
            
            return {
                'paper': paper['title'],
                'paper_id': paper.get('arxiv_id', ''),
                'analysis': analysis,
                'text_length': paper.get('text_length', 0),
                'chunks_count': len(text_chunks) if text_chunks else 0
            }
        except Exception as e:
            print(f"⚠️ 论文分析失败: {paper['title'][:50]}... - {e}")
            return None
    
    def _analyze_papers_sequentially(self, papers: List[Dict]) -> List[Dict]:
        """串行分析论文（fallback方法）"""
        print(f"📝 开始串行分析{len(papers)}篇论文...")
        analyses = []
        
        for i, paper in enumerate(papers, 1):
            print(f"  分析论文 {i}/{len(papers)}: {paper['title'][:50]}...")
            
            try:
                text_chunks = paper.get('text_chunks', [])
                analysis = self.analyze_paper_text(paper['title'], paper['abstract'], text_chunks)
                
                analyses.append({
                    'paper': paper['title'],
                    'paper_id': paper.get('arxiv_id', ''),
                    'analysis': analysis,
                    'text_length': paper.get('text_length', 0),
                    'chunks_count': len(text_chunks) if text_chunks else 0
                })
                print(f"  ✅ 完成分析")
            except Exception as e:
                print(f"  ❌ 分析失败: {e}")
        
        return analyses
    
    def analyze_multiple_papers_summary(self, paper_analyses: List[Dict], research_topic: str, depth_round: int = 1) -> str:
        """基于多篇论文的分析生成综合总结，使用专用总结API"""
        
        if not paper_analyses:
            return "没有分析的论文。"
        
        # 构建分析摘要
        analyses_text = ""
        for i, analysis in enumerate(paper_analyses[:MAX_ANAYLISE_PAPERS], 1):  # 限制最多MAX_ANAYLISE_PAPERS篇论文
            analyses_text += f"\n论文 {i}: {analysis['paper']}\n"
            analyses_text += f"分析: {analysis['analysis'][:SINGLE_ANAYLISE_LENTH]}...\n"  # 限制每个分析的长度
        
        # 截断如果太长
        analyses_text = self._truncate_content_if_needed(analyses_text, max_tokens=MAX_ANAYLISE_OUTPUT_LENGTH)
        
        depth_info = f"(第{depth_round}轮搜索)" if depth_round > 1 else ""
        
        prompt = f"""
基于对{len(paper_analyses)}篇关于"{research_topic}"的研究论文的详细分析{depth_info}，请提供一个全面的研究综述:

论文分析:
{analyses_text}

请提供:
1. **当前研究现状** (4-5个关键趋势和模式)
2. **主要技术方法** (正在使用的方法、算法、框架)
3. **关键创新和突破** (新颖和重要的内容)
4. **研究空白和挑战** (缺失或存在问题的方面)
5. **未来研究方向** (具体建议)
6. **实际应用意义** (现实世界的应用和影响)

请用清晰的章节格式回应，具体、技术化且可操作。
"""
        
        print(f"🧠 正在使用专用总结API生成研究综述...")
        return self.ask(prompt, temperature=SUMMARY_TEMPERATURE, use_summary_api=True)
    
    def evaluate_research_adequacy(self, research_summary: str, research_topic: str, total_papers_analyzed: int) -> Tuple[float, str, List[str]]:
        """
        评估研究资料的充分性，返回(评分, 评估报告, 缺失领域列表)
        
        Args:
            research_summary: 当前的研究总结
            research_topic: 研究主题
            total_papers_analyzed: 已分析的论文总数
            
        Returns:
            (adequacy_score, evaluation_report, missing_areas)
        """
        
        print(f"🔍 正在评估研究资料充分性...")
        
        prompt = f"""
作为一位资深学术研究专家，请评估关于"{research_topic}"的当前研究资料是否充分。

当前研究总结:
{research_summary}

已分析论文数量: {total_papers_analyzed}

请从以下角度进行评估:

1. **覆盖度评估**: 
   - 主要研究方向是否都有涉及
   - 关键技术方法是否全面
   - 重要应用领域是否覆盖

2. **深度评估**:
   - 理论基础是否充分
   - 技术细节是否详细
   - 实验验证是否充分

3. **时效性评估**:
   - 是否包含最新研究进展
   - 是否遗漏重要的新方法

4. **完整性评估**:
   - 是否存在明显的研究空白
   - 是否需要补充特定方向的论文

请按以下格式返回评估结果:

**充分性评分**: [0.0-1.0的分数，1.0表示完全充分]

**详细评估报告**:
[具体分析当前资料的优势和不足]

**缺失的研究领域**:
1. [具体的缺失领域1]
2. [具体的缺失领域2]
3. [具体的缺失领域3]
[如果资料充分，可以回复"无明显缺失"]

**进一步搜索建议**:
[是否建议进行进一步搜索，以及重点方向]
"""
        
        response = self.ask(prompt, temperature=0.2, use_summary_api=True)
        
        # 解析响应
        adequacy_score = self._extract_adequacy_score(response)
        missing_areas = self._extract_missing_areas(response)
        
        print(f"📊 充分性评估完成 - 评分: {adequacy_score:.2f}")
        
        return adequacy_score, response, missing_areas
    
    def _extract_adequacy_score(self, evaluation_text: str) -> float:
        """从评估文本中提取充分性评分"""
        # 寻找评分模式
        score_patterns = [
            r'充分性评分.*?([0-1]\.?\d*)',
            r'评分.*?([0-1]\.?\d*)',
            r'分数.*?([0-1]\.?\d*)',
        ]
        
        for pattern in score_patterns:
            match = re.search(pattern, evaluation_text, re.IGNORECASE)
            if match:
                try:
                    score = float(match.group(1))
                    return min(max(score, 0.0), 1.0)  # 确保在0-1范围内
                except:
                    continue
        
        # 如果没有找到明确分数，基于关键词估算
        if any(keyword in evaluation_text for keyword in ['充分', '完整', '全面', 'adequate', 'sufficient', 'comprehensive']):
            return 0.8
        elif any(keyword in evaluation_text for keyword in ['不足', '缺失', '需要补充', 'insufficient', 'lacking', 'need more']):
            return 0.4
        else:
            return 0.6  # 默认中等评分
    
    def _extract_missing_areas(self, evaluation_text: str) -> List[str]:
        """从评估文本中提取缺失的研究领域"""
        missing_areas = []
        
        # 寻找缺失领域部分
        lines = evaluation_text.split('\n')
        in_missing_section = False
        
        for line in lines:
            line = line.strip()
            
            # 检查是否进入缺失领域部分
            if any(keyword in line for keyword in ['缺失', '研究领域', 'missing', 'areas', '需要补充']):
                in_missing_section = True
                continue
            
            # 如果在缺失领域部分
            if in_missing_section:
                # 检查是否结束
                if line.startswith('**') and '建议' in line:
                    break
                
                # 提取具体领域
                if line and (line.startswith(('1.', '2.', '3.', '4.', '5.', '-', '•'))):
                    # 清理前缀
                    area = re.sub(r'^[\d\.\-•\s]+', '', line).strip()
                    if area and area != "无明显缺失":
                        missing_areas.append(area)
        
        return missing_areas[:MAX_NEW_KEYWORDS_PER_DEPTH]  # 限制数量
    
    def generate_depth_search_queries(self, research_topic: str, missing_areas: List[str], previous_queries: List[str], num_queries: int = 2) -> List[str]:
        """
        基于缺失领域生成深度搜索查询
        
        Args:
            research_topic: 原始研究主题
            missing_areas: 缺失的研究领域
            previous_queries: 之前使用的查询
            num_queries: 要生成的查询数量
            
        Returns:
            新的搜索查询列表
        """
        
        print(f"🎯 正在生成深度搜索查询...")
        
        missing_areas_text = "\n".join([f"- {area}" for area in missing_areas])
        previous_queries_text = "\n".join([f"- {query}" for query in previous_queries])
        
        prompt = f"""
基于研究资料充分性评估，需要为"{research_topic}"生成{num_queries}个新的深度搜索查询。

缺失的研究领域:
{missing_areas_text}

已使用的查询（避免重复）:
{previous_queries_text}

要求:
1. 专门针对缺失领域设计查询
2. 避免与之前查询重复
3. 只返回纯英文关键词组合，每行一个
4. 不要解释或描述，直接给出查询
5. 每个查询2-5个关键词
6. 重点关注具体的技术方法、应用领域或理论方向

示例格式:
multimodal transformer architectures
few shot learning transformers
transformer optimization techniques

现在生成{num_queries}个深度搜索查询:
"""
        
        response = self.ask(prompt, temperature=0.3)
        
        # 解析查询
        new_queries = self._parse_and_clean_queries_improved(response, num_queries)
        
        # 过滤掉与之前查询过于相似的查询
        filtered_queries = self._filter_similar_queries(new_queries, previous_queries)
        
        # 如果过滤后查询不够，生成补充查询
        if len(filtered_queries) < num_queries:
            supplement_queries = self._generate_supplement_queries(research_topic, missing_areas, filtered_queries + previous_queries)
            filtered_queries.extend(supplement_queries)
        
        final_queries = filtered_queries[:num_queries]
        print(f"🎯 生成的深度搜索查询: {final_queries}")
        
        return final_queries
    
    def _filter_similar_queries(self, new_queries: List[str], previous_queries: List[str]) -> List[str]:
        """过滤掉与之前查询过于相似的查询"""
        filtered = []
        
        for new_query in new_queries:
            is_similar = False
            new_words = set(new_query.lower().split())
            
            for prev_query in previous_queries:
                prev_words = set(prev_query.lower().split())
                
                # 计算词汇重叠度
                overlap = len(new_words.intersection(prev_words))
                similarity = overlap / max(len(new_words), len(prev_words), 1)
                
                if similarity > 0.6:  # 如果重叠度超过60%，认为太相似
                    is_similar = True
                    break
            
            if not is_similar:
                filtered.append(new_query)
        
        return filtered
    
    def _generate_supplement_queries(self, research_topic: str, missing_areas: List[str], existing_queries: List[str]) -> List[str]:
        """生成补充查询"""
        supplements = []
        
        # 从研究主题和缺失领域提取关键词
        all_keywords = self._extract_keywords_from_topic(research_topic)
        for area in missing_areas:
            all_keywords.extend(self._extract_keywords_from_topic(area))
        
        # 去重并选择重要关键词
        unique_keywords = list(set(all_keywords))[:10]
        
        # 生成简单的关键词组合
        if len(unique_keywords) >= 2:
            for i in range(0, len(unique_keywords) - 1, 2):
                if len(supplements) >= 3:  # 最多3个补充查询
                    break
                supplement = f"{unique_keywords[i]} {unique_keywords[i+1]}"
                if supplement not in existing_queries:
                    supplements.append(supplement)
        
        return supplements