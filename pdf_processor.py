import requests
import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional, Dict, List
import time
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import arxiv
import random

from config import (
    DOWNLOAD_DIR, 
    EXTRACT_FULL_PDF, 
    MAX_PAGES_TO_EXTRACT, 
    MAX_INPUT_TOKENS,
    MAX_TEXT_LENGTH,
    PDF_CHUNK_SIZE
)

class EnhancedPDFProcessor:
    def __init__(self):
        self.download_dir = Path(DOWNLOAD_DIR)
        self.download_dir.mkdir(exist_ok=True)
        
        # 🔧 增强的请求会话配置，更好地模拟真实浏览器
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        })
        
        # 支持的PDF域名和其特殊处理方法
        self.pdf_handlers = {
            'arxiv.org': self._handle_arxiv_pdf,
            'researchgate.net': self._handle_researchgate_pdf,
            'academia.edu': self._handle_academia_pdf,
            'semanticscholar.org': self._handle_semantic_scholar_pdf,
            'ieee.org': self._handle_ieee_pdf,
            'acm.org': self._handle_acm_pdf,
            'sciencedirect.com': self._handle_sciencedirect_pdf,
            'springer.com': self._handle_springer_pdf,
            'nature.com': self._handle_nature_pdf,
        }
        
        print(f"🔧 Enhanced PDF Processor 初始化完成")
        print(f"   - 支持 {len(self.pdf_handlers)} 种专门的PDF处理器")
        print(f"   - 增强的浏览器模拟")
        print(f"   - 多重备用下载机制")
    
    def process_paper(self, paper: Dict, download_dir: str) -> Optional[Dict]:
        """
        处理单篇论文：下载+提取 (增强版)
        """
        title = paper.get('title', 'Unknown')
        print(f"🔍 正在处理论文: {title}")
        
        # 🎯 多重PDF获取策略
        pdf_path = self._get_pdf_with_enhanced_strategies(paper, download_dir)
        
        if pdf_path:
            text = self.extract_text(pdf_path)
            if text:
                paper['local_path'] = str(pdf_path)
                paper['extracted_text'] = text
                paper['text_length'] = len(text)
                
                if len(text) > PDF_CHUNK_SIZE:
                    paper['text_chunks'] = self.split_text_into_chunks(text)
                    print(f"📚 论文处理完成，分为 {len(paper['text_chunks'])} 个文本块")
                else:
                    paper['text_chunks'] = [text]
                    print(f"📚 论文处理完成，单个文本块")
                
                return paper
            else:
                print("❌ 文本提取失败")
        else:
            print("❌ PDF下载失败")
        
        # Fallback：使用摘要
        if paper.get('abstract'):
            print("📝 使用摘要作为fallback")
            paper['extracted_text'] = paper['abstract']
            paper['text_length'] = len(paper['abstract'])
            paper['text_chunks'] = [paper['abstract']]
            paper['local_path'] = None
            return paper
        
        return None
    
    def _get_pdf_with_enhanced_strategies(self, paper: Dict, download_dir: str) -> Optional[Path]:
        """增强的PDF获取策略"""
        title = paper.get('title', 'Unknown')
        safe_title = self._generate_safe_filename(title)
        
        print(f"  🎯 开始增强PDF获取策略...")
        
        # 策略1: 优先处理已知的高成功率链接（arXiv等）
        pdf_links = paper.get('pdf_links', [])
        if paper.get('pdf_url'):
            pdf_links = [paper['pdf_url']] + pdf_links
        
        prioritized_links = self._prioritize_pdf_links(pdf_links)
        
        print(f"  📋 找到 {len(prioritized_links)} 个PDF链接，按优先级排序")
        
        # 策略2: 按优先级尝试下载
        for i, link in enumerate(prioritized_links):
            print(f"    尝试链接 {i+1}/{len(prioritized_links)}: {self._truncate_url_for_display(link)}")
            
            # 根据域名选择专门的处理器
            domain = self._extract_domain(link)
            if domain in self.pdf_handlers:
                print(f"      使用专门处理器: {domain}")
                pdf_path = self.pdf_handlers[domain](link, safe_title, download_dir)
            else:
                print(f"      使用通用处理器")
                pdf_path = self._download_from_url_enhanced(link, safe_title, download_dir)
            
            if pdf_path:
                print(f"    ✅ 成功下载: {domain}")
                return pdf_path
            
            # 添加延迟避免被限制
            time.sleep(random.uniform(1, 2))
        
        # 策略3: 如果有Google Scholar页面，尝试深度解析
        if paper.get('source') == 'google_scholar' and paper.get('paper_url'):
            print(f"  🔍 策略3: 深度解析Google Scholar页面")
            pdf_path = self._deep_parse_scholar_page(paper['paper_url'], safe_title, download_dir)
            if pdf_path:
                return pdf_path
        
        # 策略4: 智能搜索备用源
        print(f"  🔍 策略4: 智能搜索备用PDF源")
        pdf_path = self._intelligent_search_fallback(title, safe_title, download_dir)
        if pdf_path:
            return pdf_path
        
        print(f"  ❌ 所有PDF获取策略都失败了")
        return None
    
    def _prioritize_pdf_links(self, links: List[str]) -> List[str]:
        """按成功率对PDF链接排序"""
        def link_priority(link):
            link_lower = link.lower()
            
            # arXiv - 最高优先级
            if 'arxiv.org' in link_lower:
                return 1
            
            # 开放获取平台
            if any(domain in link_lower for domain in ['researchgate.net', 'academia.edu', 'semanticscholar.org']):
                return 2
            
            # 直接PDF文件
            if '.pdf' in link_lower:
                return 3
            
            # PMC等开放期刊
            if any(domain in link_lower for domain in ['ncbi.nlm.nih.gov', 'pubmed', 'biorxiv', 'medrxiv']):
                return 4
            
            # 机构仓库
            if any(keyword in link_lower for keyword in ['repository', 'dspace', 'eprints']):
                return 5
            
            # 出版商（成功率相对较低）
            if any(domain in link_lower for domain in ['ieee.org', 'acm.org', 'springer.com']):
                return 6
            
            # ScienceDirect等（成功率最低）
            if 'sciencedirect.com' in link_lower:
                return 7
            
            return 8
        
        return sorted(set(links), key=link_priority)  # 去重并排序
    
    def _extract_domain(self, url: str) -> str:
        """提取URL的域名"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # 移除www前缀
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return ""
    
    def _truncate_url_for_display(self, url: str, max_length: int = 80) -> str:
        """截断URL用于显示 (保留完整域名信息)"""
        if len(url) <= max_length:
            return url
        
        # 尝试保留重要部分
        parsed = urlparse(url)
        domain = parsed.netloc
        path = parsed.path
        
        if len(domain) + 10 < max_length:
            # 显示域名 + 路径的开始部分
            remaining = max_length - len(domain) - 10
            if len(path) > remaining:
                return f"{domain}{path[:remaining]}..."
            else:
                return f"{domain}{path}..."
        else:
            # 域名太长，直接截断
            return url[:max_length-3] + "..."
    
    # 🎯 专门的PDF处理器
    
    def _handle_arxiv_pdf(self, url: str, filename: str, download_dir: str) -> Optional[Path]:
        """arXiv PDF处理器"""
        try:
            # 确保使用PDF URL
            if '/abs/' in url:
                pdf_url = url.replace('/abs/', '/pdf/') + '.pdf'
            elif '/pdf/' in url and not url.endswith('.pdf'):
                pdf_url = url + '.pdf'
            else:
                pdf_url = url
            
            return self._download_from_url_enhanced(pdf_url, filename, download_dir)
            
        except Exception as e:
            print(f"      ❌ arXiv处理失败: {e}")
            return None
    
    def _handle_researchgate_pdf(self, url: str, filename: str, download_dir: str) -> Optional[Path]:
        """ResearchGate PDF处理器"""
        try:
            # ResearchGate通常需要特殊处理，先尝试直接下载
            return self._download_from_url_enhanced(url, filename, download_dir)
            
        except Exception as e:
            print(f"      ❌ ResearchGate处理失败: {e}")
            return None
    
    def _handle_academia_pdf(self, url: str, filename: str, download_dir: str) -> Optional[Path]:
        """Academia.edu PDF处理器"""
        try:
            return self._download_from_url_enhanced(url, filename, download_dir)
            
        except Exception as e:
            print(f"      ❌ Academia.edu处理失败: {e}")
            return None
    
    def _handle_semantic_scholar_pdf(self, url: str, filename: str, download_dir: str) -> Optional[Path]:
        """Semantic Scholar PDF处理器"""
        try:
            return self._download_from_url_enhanced(url, filename, download_dir)
            
        except Exception as e:
            print(f"      ❌ Semantic Scholar处理失败: {e}")
            return None
    
    def _handle_ieee_pdf(self, url: str, filename: str, download_dir: str) -> Optional[Path]:
        """IEEE PDF处理器"""
        try:
            # IEEE的PDF通常需要特殊URL格式
            if '/document/' in url:
                doc_id = re.search(r'/document/(\d+)', url)
                if doc_id:
                    pdf_url = f"https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={doc_id.group(1)}"
                    return self._download_from_url_enhanced(pdf_url, filename, download_dir)
            
            return self._download_from_url_enhanced(url, filename, download_dir)
            
        except Exception as e:
            print(f"      ❌ IEEE处理失败: {e}")
            return None
    
    def _handle_acm_pdf(self, url: str, filename: str, download_dir: str) -> Optional[Path]:
        """ACM PDF处理器"""
        try:
            # ACM的PDF链接模式
            if '/doi/' in url and '/pdf/' not in url:
                pdf_url = url.replace('/doi/', '/doi/pdf/')
                return self._download_from_url_enhanced(pdf_url, filename, download_dir)
            
            return self._download_from_url_enhanced(url, filename, download_dir)
            
        except Exception as e:
            print(f"      ❌ ACM处理失败: {e}")
            return None
    
    def _handle_sciencedirect_pdf(self, url: str, filename: str, download_dir: str) -> Optional[Path]:
        """ScienceDirect PDF处理器（增强抗反爬虫）"""
        try:
            # ScienceDirect需要特殊的请求头
            special_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://www.google.com/',  # 重要：添加Google引荐
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'cross-site',
            }
            
            # 尝试转换为PDF URL
            if '/pii/' in url:
                pdf_url = url.replace('/pii/', '/pdf/') + '.pdf'
                return self._download_with_special_headers(pdf_url, filename, download_dir, special_headers)
            
            return self._download_with_special_headers(url, filename, download_dir, special_headers)
            
        except Exception as e:
            print(f"      ❌ ScienceDirect处理失败: {e}")
            return None
    
    def _handle_springer_pdf(self, url: str, filename: str, download_dir: str) -> Optional[Path]:
        """Springer PDF处理器"""
        try:
            return self._download_from_url_enhanced(url, filename, download_dir)
            
        except Exception as e:
            print(f"      ❌ Springer处理失败: {e}")
            return None
    
    def _handle_nature_pdf(self, url: str, filename: str, download_dir: str) -> Optional[Path]:
        """Nature PDF处理器"""
        try:
            return self._download_from_url_enhanced(url, filename, download_dir)
            
        except Exception as e:
            print(f"      ❌ Nature处理失败: {e}")
            return None
    
    def _download_with_special_headers(self, url: str, filename: str, download_dir: str, headers: Dict) -> Optional[Path]:
        """使用特殊请求头下载"""
        if not url:
            return None
            
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            download_dir_path = Path(download_dir)
            file_path = download_dir_path / f"{filename}.pdf"
            
            if file_path.exists() and file_path.stat().st_size > 1024:
                print(f"        ✅ 文件已存在")
                return file_path
            
            # 创建特殊会话
            special_session = requests.Session()
            special_session.headers.update(headers)
            
            print(f"        📥 使用特殊请求头下载...")
            
            response = special_session.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '').lower()
            
            if 'application/pdf' in content_type:
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                file_size = file_path.stat().st_size
                if file_size > 1024:
                    print(f"        ✅ 下载成功: {file_size/1024:.1f} KB")
                    return file_path
                else:
                    file_path.unlink()
                    return None
            else:
                print(f"        ⚠️ 不是PDF文件: {content_type}")
                return None
            
        except Exception as e:
            print(f"        ❌ 特殊下载失败: {e}")
            return None
    
    def _download_from_url_enhanced(self, url: str, filename: str, download_dir: str) -> Optional[Path]:
        """增强的URL下载方法"""
        if not url:
            return None
            
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            download_dir_path = Path(download_dir)
            file_path = download_dir_path / f"{filename}.pdf"
            
            if file_path.exists() and file_path.stat().st_size > 1024:
                print(f"        ✅ 文件已存在")
                return file_path
            
            print(f"        📥 下载中...")
            
            # 增加随机延迟
            time.sleep(random.uniform(0.5, 1.5))
            
            response = self.session.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '').lower()
            
            if 'application/pdf' in content_type:
                # 直接是PDF
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                file_size = file_path.stat().st_size
                if file_size > 1024:
                    print(f"        ✅ 下载成功: {file_size/1024:.1f} KB")
                    return file_path
                else:
                    file_path.unlink()
                    return None
            
            elif 'text/html' in content_type:
                # HTML页面，尝试解析PDF链接
                print(f"        🔍 解析HTML页面中的PDF链接...")
                soup = BeautifulSoup(response.content, 'html.parser')
                
                pdf_links = self._extract_pdf_links_from_html(soup, url)
                
                for pdf_link in pdf_links[:3]:
                    print(f"        📥 尝试HTML中的PDF链接...")
                    pdf_path = self._download_from_url_enhanced(pdf_link, filename, download_dir)
                    if pdf_path:
                        return pdf_path
            
            return None
            
        except Exception as e:
            print(f"        ❌ 下载失败: {e}")
            return None
    
    def _extract_pdf_links_from_html(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """从HTML中提取PDF链接"""
        pdf_links = []
        
        # 查找明确的PDF链接
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text().lower()
            
            # 检查链接和文本
            if (('.pdf' in href.lower()) or 
                ('download' in text) or 
                ('pdf' in text) or
                ('full text' in text) or
                ('view pdf' in text)):
                
                full_url = urljoin(base_url, href)
                pdf_links.append(full_url)
        
        # 查找特殊的PDF按钮或链接
        pdf_selectors = [
            'a[href*=".pdf"]',
            'a[href*="download"]',
            'a[href*="pdf"]',
            '.pdf-download a',
            '.download-pdf a',
            '.full-text a'
        ]
        
        for selector in pdf_selectors:
            elements = soup.select(selector)
            for element in elements:
                href = element.get('href')
                if href:
                    full_url = urljoin(base_url, href)
                    pdf_links.append(full_url)
        
        return list(set(pdf_links))  # 去重
    
    def _deep_parse_scholar_page(self, scholar_url: str, filename: str, download_dir: str) -> Optional[Path]:
        """深度解析Google Scholar页面"""
        try:
            print(f"    🔍 深度解析Scholar页面...")
            
            # 增加随机延迟
            time.sleep(random.uniform(2, 4))
            
            response = self.session.get(scholar_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 更全面的PDF链接搜索
            pdf_links = []
            
            # 方法1: 查找直接PDF链接
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text().lower()
                
                if (self._is_potential_pdf_link(href, text)):
                    full_url = urljoin(scholar_url, href)
                    pdf_links.append(full_url)
            
            # 方法2: 查找特殊的Scholar元素
            scholar_pdf_elements = soup.find_all(['div', 'span'], class_=re.compile(r'gs_or|gs_fl|gs_ggs'))
            for element in scholar_pdf_elements:
                links = element.find_all('a', href=True)
                for link in links:
                    href = link['href']
                    if self._is_potential_pdf_link(href, link.get_text().lower()):
                        full_url = urljoin(scholar_url, href)
                        pdf_links.append(full_url)
            
            # 尝试下载找到的链接
            for pdf_link in pdf_links[:5]:  # 限制尝试次数
                print(f"        📥 尝试Scholar解析链接...")
                pdf_path = self._download_from_url_enhanced(pdf_link, filename, download_dir)
                if pdf_path:
                    return pdf_path
                time.sleep(1)
            
            return None
            
        except Exception as e:
            print(f"    ❌ Scholar深度解析失败: {e}")
            return None
    
    def _is_potential_pdf_link(self, href: str, text: str) -> bool:
        """判断是否为潜在的PDF链接"""
        href_lower = href.lower()
        text_lower = text.lower()
        
        # 明确的PDF指标
        if '.pdf' in href_lower:
            return True
        
        # 已知的PDF域名
        pdf_domains = ['arxiv.org', 'researchgate.net', 'academia.edu', 'semanticscholar.org']
        if any(domain in href_lower for domain in pdf_domains):
            return True
        
        # PDF相关的文本
        pdf_keywords = ['pdf', 'download', 'full text', 'view paper', 'get pdf', 'paper']
        if any(keyword in text_lower for keyword in pdf_keywords):
            return True
        
        # 下载类关键词
        download_keywords = ['download', 'view', 'access', 'read']
        if any(keyword in href_lower for keyword in download_keywords):
            return True
        
        return False
    
    def _intelligent_search_fallback(self, title: str, filename: str, download_dir: str) -> Optional[Path]:
        """智能多源PDF搜索备用机制"""
        print(f"    🔍 启动智能多源PDF搜索...")
        
        # 清理标题用于搜索
        clean_title = re.sub(r'[^\w\s]', ' ', title).strip()
        search_words = clean_title.split()[:8]  # 取更多关键词提高匹配率
        
        if len(search_words) < 2:
            print(f"      ⚠️ 标题关键词不足，跳过多源搜索")
            return None
        
        search_query = ' '.join(search_words)
        print(f"      🔍 搜索查询: {search_query}")
        
        # 策略1: arXiv搜索（最可靠的PDF源）
        pdf_path = self._search_arxiv_for_pdf(search_query, title, filename, download_dir)
        if pdf_path:
            return pdf_path
        
        # 策略2: scholarly库搜索
        pdf_path = self._search_scholarly_for_pdf(search_query, title, filename, download_dir)
        if pdf_path:
            return pdf_path
        
        # 策略3: DBLP搜索（通过DOI链接）
        pdf_path = self._search_dblp_for_pdf(search_query, title, filename, download_dir)
        if pdf_path:
            return pdf_path
        
        print(f"    ❌ 所有多源PDF搜索都失败了")
        return None
    
    def _search_arxiv_for_pdf(self, search_query: str, original_title: str, filename: str, download_dir: str) -> Optional[Path]:
        """从arXiv搜索相同论文的PDF"""
        try:
            print(f"      📚 在arXiv中搜索相同论文...")
            
            import arxiv
            search = arxiv.Search(
                query=search_query,
                max_results=10,  # 增加搜索结果数量
                sort_by=arxiv.SortCriterion.Relevance
            )
            
            for i, result in enumerate(search.results()):
                similarity = self._title_similarity(original_title, result.title)
                # print(f"        📄 候选 {i+1}: {result.title}")
                # print(f"           相似度: {similarity:.2f}, arXiv ID: {result.get_short_id()}")
                
                if similarity > 0.2:  # 相对宽松的匹配阈值
                    print(f"        ✅ 找到匹配论文，下载PDF...")
                    pdf_path = self._download_from_url_enhanced(result.pdf_url, filename, download_dir)
                    if pdf_path:
                        print(f"        ✅ arXiv PDF下载成功!")
                        return pdf_path
                    else:
                        print(f"        ❌ arXiv PDF下载失败")
            
            print(f"      ❌ arXiv中未找到匹配论文")
            return None
            
        except Exception as e:
            print(f"      ❌ arXiv搜索失败: {e}")
            return None
    
    def _search_scholarly_for_pdf(self, search_query: str, original_title: str, filename: str, download_dir: str) -> Optional[Path]:
        """从scholarly库搜索相同论文的PDF"""
        try:
            print(f"      📚 在scholarly中搜索相同论文...")
            
            # 检查scholarly是否可用
            try:
                from scholarly import scholarly
            except ImportError:
                print(f"        ⚠️ scholarly库不可用")
                return None
            
            search_results = scholarly.search_pubs(search_query)
            
            processed_count = 0
            for i, pub in enumerate(search_results):
                if processed_count >= 5:  # 限制处理数量避免超时
                    break
                
                try:
                    bib = pub.get('bib', {})
                    candidate_title = bib.get('title', '')
                    
                    if not candidate_title:
                        continue
                    
                    similarity = self._title_similarity(original_title, candidate_title)
                    print(f"        📄 候选 {processed_count+1}: {candidate_title}")
                    print(f"           相似度: {similarity:.2f}")
                    
                    if similarity > 0.4:  # scholarly使用稍高的匹配阈值
                        print(f"        ✅ 找到匹配论文，尝试获取PDF...")
                        
                        # 尝试多种PDF获取方式
                        pdf_urls = []
                        
                        # 方式1: 直接PDF链接
                        if bib.get('eprint'):
                            pdf_urls.append(bib['eprint'])
                        
                        # 方式2: 论文页面链接
                        if bib.get('url'):
                            pdf_urls.append(bib['url'])
                        
                        # 尝试下载找到的PDF链接
                        for pdf_url in pdf_urls:
                            print(f"          📥 尝试PDF链接...")
                            pdf_path = self._download_from_url_enhanced(pdf_url, filename, download_dir)
                            if pdf_path:
                                print(f"        ✅ scholarly PDF下载成功!")
                                return pdf_path
                        
                        print(f"        ❌ scholarly PDF链接均下载失败")
                    
                    processed_count += 1
                    
                except Exception as e:
                    print(f"        ⚠️ 处理scholarly结果出错: {e}")
                    continue
                
                # 添加延迟避免被限制
                time.sleep(0.5)
            
            print(f"      ❌ scholarly中未找到匹配论文")
            return None
            
        except Exception as e:
            print(f"      ❌ scholarly搜索失败: {e}")
            return None
    
    def _search_dblp_for_pdf(self, search_query: str, original_title: str, filename: str, download_dir: str) -> Optional[Path]:
        """从DBLP搜索相同论文的PDF（通过DOI等）"""
        try:
            print(f"      📚 在DBLP中搜索相同论文...")
            
            import xml.etree.ElementTree as ET
            
            # DBLP API搜索
            dblp_url = "https://dblp.org/search/publ/api"
            params = {
                'q': search_query,
                'format': 'xml',
                'h': 10
            }
            
            response = self.session.get(dblp_url, params=params, timeout=15)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            hits = root.findall('.//hit')
            
            for i, hit in enumerate(hits):
                try:
                    info = hit.find('info')
                    if info is None:
                        continue
                    
                    title_elem = info.find('title')
                    candidate_title = title_elem.text if title_elem is not None else ''
                    
                    if not candidate_title:
                        continue
                    
                    similarity = self._title_similarity(original_title, candidate_title)
                    print(f"        📄 候选 {i+1}: {candidate_title}")
                    print(f"           相似度: {similarity:.2f}")
                    
                    if similarity > 0.5:  # DBLP使用较高的匹配阈值
                        print(f"        ✅ 找到匹配论文，尝试获取PDF...")
                        
                        # 尝试获取DOI链接
                        doi_elem = info.find('doi')
                        if doi_elem is not None and doi_elem.text:
                            doi = doi_elem.text
                            doi_url = f"https://doi.org/{doi}"
                            print(f"          📥 尝试DOI链接: {doi}")
                            
                            pdf_path = self._download_from_url_enhanced(doi_url, filename, download_dir)
                            if pdf_path:
                                print(f"        ✅ DBLP DOI PDF下载成功!")
                                return pdf_path
                            else:
                                print(f"        ❌ DBLP DOI PDF下载失败")
                        
                        # 尝试其他链接
                        url_elem = info.find('url')
                        if url_elem is not None and url_elem.text:
                            paper_url = url_elem.text
                            print(f"          📥 尝试论文页面链接...")
                            
                            pdf_path = self._download_from_url_enhanced(paper_url, filename, download_dir)
                            if pdf_path:
                                print(f"        ✅ DBLP 页面PDF下载成功!")
                                return pdf_path
                            else:
                                print(f"        ❌ DBLP 页面PDF下载失败")
                
                except Exception as e:
                    print(f"        ⚠️ 处理DBLP结果出错: {e}")
                    continue
            
            print(f"      ❌ DBLP中未找到匹配论文")
            return None
            
        except Exception as e:
            print(f"      ❌ DBLP搜索失败: {e}")
            return None
    
    def _title_similarity(self, title1: str, title2: str) -> float:
        """计算标题相似度"""
        def clean_title(title):
            return re.sub(r'[^\w\s]', ' ', title.lower()).split()
        
        words1 = set(clean_title(title1))
        words2 = set(clean_title(title2))
        
        if not words1 or not words2:
            return 0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def _generate_safe_filename(self, title: str) -> str:
        """生成安全的文件名"""
        safe_title = re.sub(r'[^\w\s-]', '', title).strip()
        safe_title = re.sub(r'\s+', '_', safe_title)
        return safe_title[:80]
    
    def extract_text(self, pdf_path: Path) -> Optional[str]:
        """从PDF提取文本，支持完整提取或部分提取"""
        try:
            doc = fitz.open(str(pdf_path))
            text = ""
            
            # 决定要提取的页数
            if EXTRACT_FULL_PDF:
                if MAX_PAGES_TO_EXTRACT is None:
                    max_pages = doc.page_count
                    print(f"📖 提取所有 {max_pages} 页")
                else:
                    max_pages = min(MAX_PAGES_TO_EXTRACT, doc.page_count)
                    print(f"📖 提取 {max_pages}/{doc.page_count} 页")
            else:
                max_pages = min(5, doc.page_count)
                print(f"📖 提取前 {max_pages} 页")
            
            # 提取文本
            for page_num in range(max_pages):
                try:
                    page = doc[page_num]
                    page_text = page.get_text()
                    text += page_text + "\n\n"
                    
                    if (page_num + 1) % 10 == 0:
                        print(f"  进度: {page_num + 1}/{max_pages} 页")
                        
                except Exception as e:
                    print(f"⚠️ 第{page_num}页提取错误: {e}")
                    continue
            
            doc.close()
            
            # 处理文本长度限制
            if MAX_TEXT_LENGTH is not None and len(text) > MAX_TEXT_LENGTH:
                print(f"📏 文本过长 ({len(text)} 字符)，截断至 {MAX_TEXT_LENGTH} 字符")
                text = text[:MAX_TEXT_LENGTH]
            
            if len(text.strip()) > 100:
                print(f"✅ 成功提取 {len(text):,} 字符")
                return text
            else:
                print(f"⚠️ 提取的文本不足")
                return None
                
        except Exception as e:
            print(f"❌ 文本提取失败: {e}")
            return None
    
    def split_text_into_chunks(self, text: str, chunk_size: int = None) -> List[str]:
        """将长文本分割成块，便于AI处理"""
        if chunk_size is None:
            chunk_size = int(MAX_INPUT_TOKENS * 3.2)
            
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # 尝试在句号处分割，避免截断句子
            if end < len(text):
                sentence_end = text.rfind('.', start, end)
                if sentence_end > start + chunk_size // 2:
                    end = sentence_end + 1
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end
        
        print(f"📄 分割为 {len(chunks)} 个文本块")
        return chunks
    
    def get_text_summary(self, paper: Dict, max_chars: int = 2000) -> str:
        """获取论文文本的摘要版本，用于快速预览"""
        full_text = paper.get('extracted_text', '')
        
        if len(full_text) <= max_chars:
            return full_text
        
        summary = full_text[:max_chars]
        
        last_period = summary.rfind('.')
        if last_period > max_chars // 2:
            summary = summary[:last_period + 1]
        
        return summary + f"\n\n[... 已截断，总共 {len(full_text):,} 字符]"