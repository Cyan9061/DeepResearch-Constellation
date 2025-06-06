import requests
import arxiv
import re
import time
import json
import random
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, quote
from bs4 import BeautifulSoup
from tqdm import tqdm
import warnings
import difflib
from fuzzywuzzy import fuzz, process
import xml.etree.ElementTree as ET
warnings.filterwarnings('ignore')

# 尝试导入scholarly库
try:
    from scholarly import scholarly, ProxyGenerator
    SCHOLARLY_AVAILABLE = True
except ImportError:
    SCHOLARLY_AVAILABLE = False
    print("⚠️ scholarly库未安装，将跳过scholarly搜索")

try:
    from config import PAPERS_PER_QUERY, DEPTH_SEARCH_QUERIES
except ImportError:
    PAPERS_PER_QUERY = 10
    DEPTH_SEARCH_QUERIES = 2

@dataclass
class SearchFilters:
    """论文搜索过滤器配置"""
    # 时间过滤
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    # 会议过滤
    conferences: List[str] = None
    exclude_conferences: List[str] = None
    
    # 引用数过滤
    min_citations: int = 0
    max_citations: Optional[int] = None
    
    # 其他过滤
    categories: List[str] = None
    min_abstract_length: int = 10
    
    # 模糊匹配参数
    fuzzy_matching: bool = True
    similarity_threshold: int = 75  # 模糊匹配相似度阈值 (0-100)

class EnhancedMultiSourcePaperSearcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 初始化scholarly（如果可用）
        self.scholarly_available = SCHOLARLY_AVAILABLE
        if self.scholarly_available:
            try:
                # 设置代理（可选）
                # pg = ProxyGenerator()
                # scholarly.use_proxy(pg)
                print("✅ scholarly库初始化成功")
            except Exception as e:
                print(f"⚠️ scholarly库初始化失败: {e}")
                self.scholarly_available = False
        
        # 扩展的计算机领域会议数据库
        self.conference_categories = {
            'Machine Learning': ['ICML', 'NIPS', 'NeurIPS', 'ICLR', 'AISTATS', 'UAI', 'COLT', 'AAAI', 'IJCAI'],
            'Computer Vision': ['CVPR', 'ICCV', 'ECCV', 'BMVC', 'WACV', 'AAAI', 'IJCAI'],
            'Natural Language Processing': ['ACL', 'EMNLP', 'NAACL', 'COLING', 'EACL', 'AAAI', 'IJCAI'],
            'Data Mining': ['KDD', 'ICDM', 'SDM', 'WSDM', 'CIKM', 'WWW'],
            'Systems': ['OSDI', 'SOSP', 'NSDI', 'SIGCOMM', 'MOBICOM', 'INFOCOM'],
            'Security': ['CCS', 'S&P', 'USENIX Security', 'NDSS', 'OAKLAND'],
            'Theory': ['STOC', 'FOCS', 'SODA', 'ICALP', 'ITCS'],
            'HCI': ['CHI', 'UIST', 'CSCW', 'UBICOMP', 'IUI'],
            'Graphics': ['SIGGRAPH', 'SIGGRAPH Asia', 'EUROGRAPHICS', 'I3D'],
            'Databases': ['SIGMOD', 'VLDB', 'ICDE', 'PODS']
        }
        
        # 会议映射（用于模糊匹配）
        self.conference_mappings = {
            # Machine Learning
            'ICML': ['International Conference on Machine Learning', 'ICML', 'PMLR'],
            'NIPS': ['Neural Information Processing Systems', 'NeurIPS', 'NIPS', 'Advances in Neural Information Processing Systems'],
            'NeurIPS': ['Neural Information Processing Systems', 'NeurIPS', 'NIPS', 'Conference and Workshop on Neural Information Processing Systems', 'Advances in Neural Information Processing Systems'],
            'ICLR': ['International Conference on Learning Representations', 'ICLR'],
            'AISTATS': ['International Conference on Artificial Intelligence and Statistics', 'AISTATS', 'PMLR'],
            'UAI': ['Conference on Uncertainty in Artificial Intelligence', 'UAI'],
            'COLT': ['Conference on Learning Theory', 'COLT', 'Conference on Computational Learning Theory'],
            'AAAI': ['AAAI Conference on Artificial Intelligence', 'AAAI', 'Association for the Advancement of Artificial Intelligence'],
            'IJCAI': ['International Joint Conference on Artificial Intelligence', 'IJCAI'],
            
            # Computer Vision  
            'CVPR': ['IEEE Conference on Computer Vision and Pattern Recognition', 'CVPR', 'IEEE / CVF Computer Vision and Pattern Recognition Conference', 'Computer Vision and Pattern Recognition'],
            'ICCV': ['International Conference on Computer Vision', 'ICCV', 'IEEE International Conference on Computer Vision'],
            'ECCV': ['European Conference on Computer Vision', 'ECCV'],
            'BMVC': ['British Machine Vision Conference', 'BMVC'],
            'WACV': ['Winter Conference on Applications of Computer Vision', 'WACV', 'IEEE Winter Conference on Applications of Computer Vision'],
            
            # Natural Language Processing
            'ACL': ['Annual Meeting of the Association for Computational Linguistics', 'ACL', 'Association for Computational Linguistics', 'Proceedings of the ACL'],
            'EMNLP': ['Conference on Empirical Methods in Natural Language Processing', 'EMNLP', 'Empirical Methods in Natural Language Processing'],
            'NAACL': ['Conference of the North American Chapter of the Association for Computational Linguistics', 'NAACL', 'NAACL-HLT', 'North American Chapter of the Association for Computational Linguistics'],
            'COLING': ['International Conference on Computational Linguistics', 'COLING'],
            'EACL': ['Conference of the European Chapter of the Association for Computational Linguistics', 'EACL', 'European Chapter of the Association for Computational Linguistics'],
            'TACL': ['Transactions of the Association for Computational Linguistics', 'TACL'],
            
            # Data Mining
            'KDD': ['ACM SIGKDD Conference on Knowledge Discovery and Data Mining', 'KDD', 'Knowledge Discovery and Data Mining'],
            'ICDM': ['IEEE International Conference on Data Mining', 'ICDM', 'International Conference on Data Mining'],
            'SDM': ['SIAM International Conference on Data Mining', 'SDM'],
            'WSDM': ['ACM International Conference on Web Search and Data Mining', 'WSDM', 'Web Search and Data Mining'],
            'CIKM': ['ACM International Conference on Information and Knowledge Management', 'CIKM'],
            'WWW': ['International World Wide Web Conference', 'WWW', 'The Web Conference', 'World Wide Web Conference'],
            
            # Systems
            'OSDI': ['USENIX Symposium on Operating Systems Design and Implementation', 'OSDI', 'Operating Systems Design and Implementation'],
            'SOSP': ['ACM Symposium on Operating Systems Principles', 'SOSP', 'ACM SIGOPS Symposium on Operating Systems Principles', 'Symposium on Operating Systems Principles'],
            'NSDI': ['USENIX Symposium on Networked Systems Design and Implementation', 'NSDI', 'Networked Systems Design and Implementation'],
            'SIGCOMM': ['ACM SIGCOMM Conference', 'SIGCOMM', 'ACM Conference on Data Communication'],
            'MOBICOM': ['ACM International Conference on Mobile Computing and Networking', 'MOBICOM', 'MobiCom'],
            'INFOCOM': ['IEEE International Conference on Computer Communications', 'INFOCOM', 'IEEE INFOCOM'],
            
            # Security
            'CCS': ['ACM Conference on Computer and Communications Security', 'CCS', 'ACM CCS'],
            'S&P': ['IEEE Symposium on Security and Privacy', 'S&P', 'IEEE S&P', 'Oakland', 'IEEE Security and Privacy'],
            'USENIX Security': ['USENIX Security Symposium', 'USENIX Security', 'Security Symposium'],
            'NDSS': ['Network and Distributed System Security Symposium', 'NDSS'],
            'OAKLAND': ['IEEE Symposium on Security and Privacy', 'Oakland', 'S&P', 'IEEE S&P'],
            
            # Theory
            'STOC': ['ACM Symposium on Theory of Computing', 'STOC', 'Symposium on Theory of Computing'],
            'FOCS': ['IEEE Symposium on Foundations of Computer Science', 'FOCS', 'Foundations of Computer Science'],
            'SODA': ['ACM-SIAM Symposium on Discrete Algorithms', 'SODA', 'Symposium on Discrete Algorithms'],
            'ICALP': ['International Colloquium on Automata, Languages and Programming', 'ICALP'],
            'ITCS': ['Innovations in Theoretical Computer Science', 'ITCS', 'Innovation in Theoretical Computer Science'],
            
            # HCI
            'CHI': ['ACM Conference on Human Factors in Computing Systems', 'CHI', 'Human Factors in Computing Systems'],
            'UIST': ['ACM Symposium on User Interface Software and Technology', 'UIST', 'User Interface Software and Technology'],
            'CSCW': ['ACM Conference on Computer-Supported Cooperative Work and Social Computing', 'CSCW'],
            'UBICOMP': ['ACM International Joint Conference on Pervasive and Ubiquitous Computing', 'UbiComp', 'UBICOMP'],
            'IUI': ['ACM International Conference on Intelligent User Interfaces', 'IUI', 'Intelligent User Interfaces'],
            
            # Graphics
            'SIGGRAPH': ['ACM SIGGRAPH Conference', 'SIGGRAPH', 'Special Interest Group on Computer Graphics and Interactive Techniques'],
            'SIGGRAPH Asia': ['ACM SIGGRAPH Conference and Exhibition on Computer Graphics and Interactive Techniques in Asia', 'SIGGRAPH Asia'],
            'EUROGRAPHICS': ['Annual Conference of the European Association for Computer Graphics', 'Eurographics', 'EUROGRAPHICS'],
            'I3D': ['ACM SIGGRAPH Symposium on Interactive 3D Graphics and Games', 'I3D', 'Interactive 3D Graphics'],
            
            # Databases
            'SIGMOD': ['ACM SIGMOD Conference on Management of Data', 'SIGMOD', 'PACMMOD', 'Proceedings of the ACM on Management of Data', 'International Conference on Management of Data'],
            'VLDB': ['International Conference on Very Large Data Bases', 'VLDB', 'Very Large Data Bases', 'PVLDB', 'Proceedings of the VLDB Endowment'],
            'ICDE': ['IEEE International Conference on Data Engineering', 'ICDE', 'International Conference on Data Engineering'],
            'PODS': ['ACM SIGMOD-SIGACT-SIGAI Symposium on Principles of Database Systems', 'PODS', 'Principles of Database Systems'],
            
            # Additional important conferences and journals
            'JMLR': ['Journal of Machine Learning Research', 'JMLR'],
            'PMLR': ['Proceedings of Machine Learning Research', 'PMLR', 'JMLR Workshop and Conference Proceedings'],
            'CL': ['Computational Linguistics', 'CL'],
            'TODS': ['ACM Transactions on Database Systems', 'TODS'],
            'VLDBJ': ['VLDB Journal', 'VLDBJ', 'The VLDB Journal'],
            'TKDE': ['IEEE Transactions on Knowledge and Data Engineering', 'TKDE'],
            'TPAMI': ['IEEE Transactions on Pattern Analysis and Machine Intelligence', 'TPAMI'],
            'JAIR': ['Journal of Artificial Intelligence Research', 'JAIR'],
            'AIJ': ['Artificial Intelligence', 'AIJ', 'Artificial Intelligence Journal'],
            'TOCS': ['ACM Transactions on Computer Systems', 'TOCS'],
            'TON': ['IEEE/ACM Transactions on Networking', 'TON'],
        }
        
        # arXiv类别映射
        self.category_mappings = {
            'machine_learning': ['cs.LG', 'cs.AI', 'stat.ML'],
            'computer_vision': ['cs.CV'],
            'nlp': ['cs.CL', 'cs.AI'],
            'systems': ['cs.DC', 'cs.OS', 'cs.NI'],
            'theory': ['cs.DS', 'cs.CC', 'cs.DM'],
            'security': ['cs.CR'],
            'databases': ['cs.DB'],
            'hci': ['cs.HC'],
            'graphics': ['cs.GR'],
            'robotics': ['cs.RO'],
            'all_cs': ['cs.*']
        }
        
        print(f"🔧 Enhanced Multi-Source Paper Searcher 初始化完成")
        print(f"   - 主要搜索源: Google Scholar")
        print(f"   - 补充搜索源: {'scholarly, ' if self.scholarly_available else ''}DBLP, arXiv")
        print(f"   - 模糊匹配: 启用")
        print(f"   - 支持 {len(self.conference_mappings)} 个主要会议")
        print(f"   - 支持 {len(self.conference_categories)} 个领域分类")
    
    def fuzzy_match_title(self, title1: str, title2: str, threshold: int = 75) -> bool:
        """模糊匹配两个标题"""
        if not title1 or not title2:
            return False
        
        # 清理标题
        clean1 = self._clean_text_for_matching(title1)
        clean2 = self._clean_text_for_matching(title2)
        
        # 使用多种匹配算法
        ratio = fuzz.ratio(clean1, clean2)
        partial_ratio = fuzz.partial_ratio(clean1, clean2)
        token_sort_ratio = fuzz.token_sort_ratio(clean1, clean2)
        token_set_ratio = fuzz.token_set_ratio(clean1, clean2)
        
        # 取最高分
        max_similarity = max(ratio, partial_ratio, token_sort_ratio, token_set_ratio)
        
        return max_similarity >= threshold
    
    def _clean_text_for_matching(self, text: str) -> str:
        """清理文本用于匹配"""
        # 转小写
        text = text.lower()
        # 移除特殊字符
        text = re.sub(r'[^\w\s]', ' ', text)
        # 标准化空格
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def fuzzy_match_conference(self, paper_text: str, target_conferences: List[str], threshold: int = 70) -> bool:
        """模糊匹配会议名称"""
        if not target_conferences:
            return True  # 如果没有指定会议，则通过
        
        paper_text_clean = self._clean_text_for_matching(paper_text)
        
        for conf in target_conferences:
            # 检查会议简称
            if fuzz.partial_ratio(conf.lower(), paper_text_clean) >= threshold:
                return True
            
            # 检查会议全称
            if conf in self.conference_mappings:
                for conf_name in self.conference_mappings[conf]:
                    conf_name_clean = self._clean_text_for_matching(conf_name)
                    if fuzz.partial_ratio(conf_name_clean, paper_text_clean) >= threshold:
                        return True
        
        return False
    
    def search_google_scholar(self, query: str, max_results: int) -> List[Dict]:
        """在Google Scholar中搜索论文（原有方法）"""
        print(f"🔍 在Google Scholar中搜索: {query}")
        
        papers = []
        start = 0
        
        while len(papers) < max_results:
            url = "https://scholar.google.com/scholar"
            params = {
                'q': query,
                'start': start,
                'hl': 'en'
            }
            
            try:
                # 随机延迟防止被封
                time.sleep(random.uniform(2, 5))
                
                response = self.session.get(url, params=params, timeout=15)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                results = soup.find_all('div', {'class': 'gs_r gs_or gs_scl'})
                
                if not results:
                    print(f"  在第{start//10 + 1}页未找到更多结果")
                    break
                
                for result in results:
                    if len(papers) >= max_results:
                        break
                    
                    paper_info = self._parse_scholar_result(result)
                    if paper_info:
                        papers.append(paper_info)
                
                start += 10
                
            except Exception as e:
                print(f"  ⚠️ Google Scholar搜索出错: {e}")
                break
        
        print(f"  ✅ Google Scholar找到 {len(papers)} 篇论文")
        return papers
    
    def search_scholarly_backup(self, query: str, max_results: int) -> List[Dict]:
        """使用scholarly库作为backup搜索"""
        if not self.scholarly_available:
            return []
        
        print(f"🔍 使用scholarly库搜索: {query}")
        
        papers = []
        try:
            search_query = scholarly.search_pubs(query)
            
            for i, pub in enumerate(search_query):
                if i >= max_results:
                    break
                
                try:
                    # 获取详细信息
                    pub_filled = scholarly.fill(pub)
                    
                    # 解析发表年份
                    pub_year = None
                    if 'pub_year' in pub_filled and pub_filled['pub_year']:
                        try:
                            pub_year = int(pub_filled['pub_year'])
                        except:
                            pass
                    
                    # 解析引用数
                    citations = 0
                    if 'num_citations' in pub_filled:
                        citations = pub_filled['num_citations'] or 0
                    
                    paper = {
                        'title': pub_filled.get('title', ''),
                        'authors': [author.get('name', '') for author in pub_filled.get('author', [])],
                        'abstract': pub_filled.get('abstract', ''),
                        'published': datetime(pub_year, 1, 1) if pub_year else None,
                        'published_str': str(pub_year) if pub_year else "Unknown",
                        'citations': citations,
                        'paper_url': pub_filled.get('pub_url', ''),
                        'pdf_url': pub_filled.get('eprint_url', ''),
                        'pdf_links': [pub_filled.get('eprint_url')] if pub_filled.get('eprint_url') else [],
                        'source': 'scholarly',
                        'venue': pub_filled.get('venue', ''),
                        'authors_text': ', '.join([author.get('name', '') for author in pub_filled.get('author', [])])
                    }
                    
                    papers.append(paper)
                    
                except Exception as e:
                    print(f"    ⚠️ 处理scholarly结果出错: {e}")
                    continue
                
                # 添加延迟避免被限制
                time.sleep(1)
            
            print(f"  ✅ scholarly找到 {len(papers)} 篇论文")
            
        except Exception as e:
            print(f"  ❌ scholarly搜索失败: {e}")
        
        return papers
    
    def search_dblp_backup(self, query: str, max_results: int) -> List[Dict]:
        """使用DBLP作为backup搜索"""
        print(f"🔍 在DBLP中搜索: {query}")
        
        papers = []
        try:
            # DBLP API搜索
            dblp_url = "https://dblp.org/search/publ/api"
            params = {
                'q': query,
                'format': 'xml',
                'h': max_results
            }
            
            response = self.session.get(dblp_url, params=params, timeout=10)
            response.raise_for_status()
            
            # 解析XML响应
            root = ET.fromstring(response.content)
            
            for hit in root.findall('.//hit'):
                try:
                    info = hit.find('info')
                    if info is None:
                        continue
                    
                    # 提取基本信息
                    title = info.find('title')
                    title_text = title.text if title is not None else ''
                    
                    # 提取作者
                    authors = []
                    for author in info.findall('authors/author'):
                        if author.text:
                            authors.append(author.text)
                    
                    # 提取年份
                    year_elem = info.find('year')
                    year = None
                    if year_elem is not None and year_elem.text:
                        try:
                            year = int(year_elem.text)
                        except:
                            pass
                    
                    # 提取会议/期刊信息
                    venue = info.find('venue')
                    venue_text = venue.text if venue is not None else ''
                    
                    # 提取DOI/URL
                    doi = info.find('doi')
                    doi_text = doi.text if doi is not None else ''
                    paper_url = f"https://doi.org/{doi_text}" if doi_text else ''
                    
                    paper = {
                        'title': title_text,
                        'authors': authors,
                        'abstract': '',  # DBLP通常不提供摘要
                        'published': datetime(year, 1, 1) if year else None,
                        'published_str': str(year) if year else "Unknown",
                        'citations': 0,  # DBLP不提供引用数
                        'paper_url': paper_url,
                        'pdf_url': None,
                        'pdf_links': [],
                        'source': 'dblp',
                        'venue': venue_text,
                        'doi': doi_text,
                        'authors_text': ', '.join(authors)
                    }
                    
                    papers.append(paper)
                    
                except Exception as e:
                    print(f"    ⚠️ 解析DBLP结果出错: {e}")
                    continue
            
            print(f"  ✅ DBLP找到 {len(papers)} 篇论文")
            
        except Exception as e:
            print(f"  ❌ DBLP搜索失败: {e}")
        
        return papers
    
    def search_arxiv_backup(self, query: str, max_results: int) -> List[Dict]:
        """在arXiv中搜索论文作为备用（原有方法，稍作修改）"""
        print(f"🔍 在arXiv中搜索: {query}")
        
        try:
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance
            )
            
            papers = []
            for result in tqdm(search.results(), desc="获取arXiv论文"):
                paper = {
                    'title': result.title,
                    'authors': [author.name for author in result.authors],
                    'abstract': result.summary,
                    'published': result.published,
                    'published_str': result.published.strftime('%Y-%m-%d'),
                    'pdf_url': result.pdf_url,
                    'pdf_links': [result.pdf_url],
                    'arxiv_id': result.get_short_id(),
                    'categories': result.categories,
                    'primary_category': result.primary_category,
                    'citations': 0,  # arXiv通常没有引用数
                    'source': 'arxiv',
                    'paper_url': result.entry_id,
                    'authors_text': ', '.join([author.name for author in result.authors])
                }
                papers.append(paper)
            
            print(f"  ✅ arXiv找到 {len(papers)} 篇论文")
            return papers
            
        except Exception as e:
            print(f"  ❌ arXiv搜索失败: {e}")
            return []
    
    def search_papers_multi_source(self, query: str, filters: SearchFilters) -> List[Dict]:
        """多源搜索论文，增强版"""
        print(f"🔍 开始多源搜索: {query}")
        
        # 验证查询
        if not query or query.strip() == "" or query.strip() == "--":
            print("⚠️ 查询为空或无效，跳过...")
            return []
        
        all_papers = []
        
        try:
            # 第一级：Google Scholar搜索
            print(f"📊 第一级搜索 - Google Scholar...")
            scholar_papers = self.search_google_scholar(query, PAPERS_PER_QUERY)
            all_papers.extend(scholar_papers)
            
            # 检查是否需要补充搜索
            if len(scholar_papers) < PAPERS_PER_QUERY:
                remaining_needed = PAPERS_PER_QUERY - len(scholar_papers)
                
                # 第二级：scholarly备用搜索
                if self.scholarly_available:
                    print(f"📊 第二级搜索 - scholarly库...")
                    scholarly_papers = self.search_scholarly_backup(query, remaining_needed)
                    all_papers.extend(scholarly_papers)
                    remaining_needed -= len(scholarly_papers)
                
                # 第三级：DBLP备用搜索
                if remaining_needed > 0:
                    print(f"📊 第三级搜索 - DBLP...")
                    dblp_papers = self.search_dblp_backup(query, remaining_needed)
                    all_papers.extend(dblp_papers)
                    remaining_needed -= len(dblp_papers)
                
                # 第四级：arXiv最终备用
                if remaining_needed > 0:
                    print(f"📊 第四级搜索 - arXiv...")
                    arxiv_papers = self.search_arxiv_backup(query, remaining_needed)
                    all_papers.extend(arxiv_papers)
            
            # 应用增强过滤器（包含模糊匹配）
            filtered_papers = []
            for paper in all_papers:
                if self._apply_enhanced_filters(paper, filters):
                    validated_paper = self._validate_paper_data(paper)
                    filtered_papers.append(validated_paper)
            
            print(f"✅ 多源搜索完成，过滤后剩余 {len(filtered_papers)} 篇论文")
            return filtered_papers
            
        except Exception as e:
            print(f"❌ 多源搜索失败 '{query}': {e}")
            return []
    
    def _apply_enhanced_filters(self, paper: Dict, filters: SearchFilters) -> bool:
        """应用增强过滤条件（包含模糊匹配）"""
        
        # 时间过滤
        if paper.get('published'):
            if filters.start_date and paper['published'] < filters.start_date:
                return False
            if filters.end_date and paper['published'] > filters.end_date:
                return False
        
        # 引用数过滤
        citations = paper.get('citations', 0)
        if citations < filters.min_citations:
            return False
        if filters.max_citations is not None and citations > filters.max_citations:
            return False
        
        # 会议过滤（使用模糊匹配）
        if filters.conferences:
            search_text = (paper.get('title', '') + ' ' + 
                          paper.get('authors_text', '') + ' ' + 
                          paper.get('venue', '') + ' ' +
                          ' '.join(paper.get('authors', []))).lower()
            
            if filters.fuzzy_matching:
                # 使用模糊匹配
                if not self.fuzzy_match_conference(search_text, filters.conferences, 
                                                 threshold=filters.similarity_threshold):
                    return False
            else:
                # 使用精确匹配
                found_conference = False
                for conf in filters.conferences:
                    if conf in self.conference_mappings:
                        conf_names = [name.lower() for name in self.conference_mappings[conf]]
                        if any(name in search_text for name in conf_names):
                            found_conference = True
                            break
                    if conf.lower() in search_text:
                        found_conference = True
                        break
                
                if not found_conference:
                    return False
        
        # 排除会议（也使用模糊匹配）
        if filters.exclude_conferences:
            search_text = (paper.get('title', '') + ' ' + 
                          paper.get('authors_text', '') + ' ' + 
                          paper.get('venue', '') + ' ' +
                          ' '.join(paper.get('authors', []))).lower()
            
            for conf in filters.exclude_conferences:
                if filters.fuzzy_matching:
                    if self.fuzzy_match_conference(search_text, [conf], 
                                                 threshold=filters.similarity_threshold):
                        return False
                else:
                    if conf in self.conference_mappings:
                        conf_names = [name.lower() for name in self.conference_mappings[conf]]
                        if any(name in search_text for name in conf_names):
                            return False
                    if conf.lower() in search_text:
                        return False
        
        # arXiv类别过滤（仅对arXiv论文有效）
        if filters.categories and paper.get('source') == 'arxiv':
            paper_categories = paper.get('categories', [])
            category_match = False
            for filter_cat in filters.categories:
                if filter_cat.endswith('.*'):
                    prefix = filter_cat[:-2]
                    if any(cat.startswith(prefix) for cat in paper_categories):
                        category_match = True
                        break
                else:
                    if filter_cat in paper_categories:
                        category_match = True
                        break
            
            if not category_match:
                return False
        
        # 摘要长度过滤
        if len(paper.get('abstract', '')) < filters.min_abstract_length:
            return False
        
        return True
    
    def _validate_paper_data(self, paper: Dict) -> Dict:
        """验证并标准化论文数据"""
        validated_paper = paper.copy()
        
        # 确保必需字段存在
        required_fields = {
            'title': 'Unknown Title',
            'authors': [],
            'abstract': '',
            'citations': 0,
            'source': 'unknown',
            'published_str': 'Unknown'
        }
        
        for field, default_value in required_fields.items():
            if field not in validated_paper:
                validated_paper[field] = default_value
        
        # 确保pdf_url字段存在
        if 'pdf_url' not in validated_paper or not validated_paper['pdf_url']:
            pdf_links = validated_paper.get('pdf_links', [])
            if pdf_links:
                validated_paper['pdf_url'] = pdf_links[0]
            else:
                validated_paper['pdf_url'] = None
        
        # 确保authors是列表格式
        if isinstance(validated_paper['authors'], str):
            validated_paper['authors'] = [validated_paper['authors']]
        elif not validated_paper['authors']:
            validated_paper['authors'] = ['Unknown Author']
        
        # 确保citations是数字
        try:
            validated_paper['citations'] = int(validated_paper.get('citations', 0))
        except (ValueError, TypeError):
            validated_paper['citations'] = 0
        
        return validated_paper
    
    def search_multiple_queries_enhanced(self, queries: List[str], filters: SearchFilters) -> List[Dict]:
        """使用增强过滤器和多源搜索"""
        all_papers = []
        max_tries = 3
        
        while len(all_papers) < 1 and max_tries > 0:
            max_tries -= 1
            print(f"🔄 开始搜索轮次 {3 - max_tries}")
            
            for i, query in enumerate(queries):
                if query and query.strip():
                    print(f"\n📝 执行查询 {i+1}/{len(queries)}: {query}")
                    papers = self.search_papers_multi_source(query, filters)
                    all_papers.extend(papers)
                    
                    print(f"  本次查询找到: {len(papers)} 篇论文")
                    print(f"  累计找到: {len(all_papers)} 篇论文")
                    
                    # 查询间延迟
                    time.sleep(2)
            
            time.sleep(3)  # 轮次间延迟
        
        # 增强去重（使用模糊匹配）
        unique_papers = self._deduplicate_papers_enhanced(all_papers, filters)
        
        # 验证数据格式
        validated_papers = []
        for paper in unique_papers:
            validated_paper = self._validate_paper_data(paper)
            validated_papers.append(validated_paper)
        
        # 按多个维度排序
        sorted_papers = self._sort_papers_by_relevance(validated_papers, filters)
        
        print(f"🎉 多源搜索完成！")
        print(f"  总计找到: {len(all_papers)} 篇论文")
        print(f"  去重后剩余: {len(unique_papers)} 篇论文")
        print(f"  最终返回: {len(sorted_papers)} 篇论文")
        
        # 显示来源统计
        source_stats = {}
        for paper in sorted_papers:
            source = paper.get('source', 'unknown')
            source_stats[source] = source_stats.get(source, 0) + 1
        
        if source_stats:
            print(f"📊 来源分布: {', '.join([f'{k}:{v}' for k, v in source_stats.items()])}")
        
        return sorted_papers
    
    def _deduplicate_papers_enhanced(self, papers: List[Dict], filters: SearchFilters) -> List[Dict]:
        """增强的去重算法（使用模糊匹配）"""
        if not papers:
            return []
        
        unique_papers = []
        seen_titles = set()
        seen_arxiv_ids = set()
        
        for paper in papers:
            arxiv_id = paper.get('arxiv_id', '')
            title = paper.get('title', '')
            
            # 检查arXiv ID重复
            if arxiv_id and arxiv_id in seen_arxiv_ids:
                continue
            
            # 检查标题重复（模糊匹配）
            is_duplicate = False
            if title and filters.fuzzy_matching:
                for seen_title in seen_titles:
                    if self.fuzzy_match_title(title, seen_title, 
                                            threshold=filters.similarity_threshold + 10):  # 去重时使用更高阈值
                        is_duplicate = True
                        break
            else:
                # 精确匹配
                title_normalized = self._normalize_title(title)
                if title_normalized in seen_titles:
                    is_duplicate = True
            
            if not is_duplicate:
                unique_papers.append(paper)
                if title:
                    seen_titles.add(title)
                if arxiv_id:
                    seen_arxiv_ids.add(arxiv_id)
        
        return unique_papers
    
    def _normalize_title(self, title: str) -> str:
        """标准化标题用于去重"""
        normalized = re.sub(r'[^\w\s]', ' ', title.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def _sort_papers_by_relevance(self, papers: List[Dict], filters: SearchFilters) -> List[Dict]:
        """按相关性对论文排序"""
        def relevance_score(paper):
            score = 0
            
            # 引用数权重
            citations = paper.get('citations', 0)
            score += min(citations / 100, 10)
            
            # 时间权重
            pub_date = paper.get('published')
            if pub_date:
                if hasattr(pub_date, 'replace'):
                    pub_date = pub_date.replace(tzinfo=None)
                days_old = (datetime.now() - pub_date).days
                time_score = max(0, 5 - (days_old / 365))
                score += time_score
            
            # 来源权重（Google Scholar > scholarly > DBLP > arXiv）
            source_weights = {
                'google_scholar': 4,
                'scholarly': 3,
                'dblp': 2,
                'arxiv': 1
            }
            score += source_weights.get(paper.get('source', 'unknown'), 0)
            
            # 会议匹配权重
            if filters.conferences:
                search_text = (paper.get('title', '') + ' ' + 
                              paper.get('authors_text', '') + ' ' +
                              paper.get('venue', '') + ' ' +
                              ' '.join(paper.get('authors', []))).lower()
                
                if filters.fuzzy_matching:
                    if self.fuzzy_match_conference(search_text, filters.conferences, 
                                                 threshold=filters.similarity_threshold):
                        score += 5
                else:
                    for conf in filters.conferences:
                        if conf.lower() in search_text:
                            score += 5
                            break
            
            return score
        
        return sorted(papers, key=relevance_score, reverse=True)
    
    def _parse_scholar_result(self, result) -> Optional[Dict]:
        """解析Google Scholar搜索结果（原有方法）"""
        try:
            # 获取标题
            title_elem = result.find('h3', {'class': 'gs_rt'})
            if not title_elem:
                return None
            
            title_link = title_elem.find('a')
            title = title_link.get_text() if title_link else title_elem.get_text()
            paper_url = title_link.get('href') if title_link else None
            
            # 获取作者和来源信息
            authors_elem = result.find('div', {'class': 'gs_a'})
            authors_text = authors_elem.get_text() if authors_elem else ""
            
            # 尝试解析年份
            published_year = None
            year_match = re.search(r'\b(19|20)\d{2}\b', authors_text)
            if year_match:
                published_year = int(year_match.group())
            
            # 获取摘要
            abstract_elem = result.find('div', {'class': 'gs_rs'})
            abstract = abstract_elem.get_text() if abstract_elem else ""
            
            # 获取引用数
            citations = 0
            cited_elem = result.find('div', {'class': 'gs_fl'})
            if cited_elem:
                cited_links = cited_elem.find_all('a')
                for link in cited_links:
                    link_text = link.get_text()
                    if 'Cited by' in link_text:
                        try:
                            citations = int(re.search(r'Cited by (\d+)', link_text).group(1))
                        except:
                            citations = 0
                        break
            
            # 查找PDF链接
            pdf_links = []
            pdf_elem = result.find('div', {'class': 'gs_or_ggsm'})
            if pdf_elem:
                pdf_link = pdf_elem.find('a')
                if pdf_link and pdf_link.get('href'):
                    pdf_links.append(pdf_link.get('href'))
            
            # 查找其他格式链接
            all_links = result.find_all('a')
            for link in all_links:
                href = link.get('href')
                if href and ('.pdf' in href.lower() or 'arxiv.org' in href):
                    pdf_links.append(href)
            
            main_pdf_url = pdf_links[0] if pdf_links else None
            
            return {
                'title': title.strip(),
                'authors': [author.strip() for author in authors_text.split(',')[:5]],
                'abstract': abstract.strip(),
                'published': datetime(published_year, 1, 1) if published_year else None,
                'published_str': str(published_year) if published_year else "Unknown",
                'citations': citations,
                'paper_url': paper_url,
                'pdf_url': main_pdf_url,
                'pdf_links': list(set(pdf_links)),
                'source': 'google_scholar',
                'authors_text': authors_text
            }
        
        except Exception as e:
            return None
    
    def display_search_results(self, papers: List[Dict], max_display: int = 10):
        """显示搜索结果摘要"""
        if not papers:
            print("📭 没有找到符合条件的论文")
            return
        
        print(f"\n📋 多源搜索结果 (显示前{min(len(papers), max_display)}篇):")
        print("=" * 80)
        
        for i, paper in enumerate(papers[:max_display], 1):
            print(f"\n{i}. {paper['title']}")
            
            if isinstance(paper.get('authors'), list):
                authors_display = ', '.join(paper['authors'][:3])
                if len(paper['authors']) > 3:
                    authors_display += '...'
            else:
                authors_display = str(paper.get('authors', 'Unknown'))[:100]
            
            print(f"   作者: {authors_display}")
            print(f"   发表日期: {paper.get('published_str', 'Unknown')}")
            print(f"   来源: {paper.get('source', 'unknown')}")
            print(f"   引用数: {paper.get('citations', 0)}")
            
            if paper.get('venue'):
                print(f"   会议/期刊: {paper['venue']}")
            
            if paper.get('arxiv_id'):
                print(f"   arXiv ID: {paper['arxiv_id']}")
            
            if paper.get('doi'):
                print(f"   DOI: {paper['doi']}")
            
            # 显示摘要前150字符
            abstract = paper.get('abstract', '')
            abstract_preview = abstract[:150] + "..." if len(abstract) > 150 else abstract
            print(f"   摘要: {abstract_preview}")
            
            if paper.get('pdf_url'):
                print(f"   PDF: {paper['pdf_url']}")
            elif paper.get('pdf_links'):
                print(f"   PDF链接: {len(paper['pdf_links'])} 个可用链接")
        
        if len(papers) > max_display:
            print(f"\n... 还有 {len(papers) - max_display} 篇论文未显示")

    def get_user_search_preferences(self) -> SearchFilters:
        """获取用户的搜索偏好设置（增强版）"""
        print("\n=== 增强型多源搜索配置 ===")
        
        # 模糊匹配设置
        print(f"\n🎯 模糊匹配设置:")
        fuzzy_choice = True#input("是否启用模糊匹配? (Y/n): ").strip().lower()
        fuzzy_matching = fuzzy_choice != 'n'
        
        similarity_threshold = 75  # 默认阈值
        if fuzzy_matching:
            threshold_input = 75#input("模糊匹配相似度阈值 (50-100, 默认75): ").strip()
            if threshold_input.isdigit():
                threshold = int(threshold_input)
                if 50 <= threshold <= 100:
                    similarity_threshold = threshold
                    print(f"✅ 相似度阈值设置为: {similarity_threshold}")
                else:
                    print("⚠️ 阈值超出范围，使用默认值75")
            print(f"✅ 模糊匹配已启用，阈值: {similarity_threshold}")
        else:
            print("✅ 使用精确匹配")
        
        # 显示可用会议
        all_conferences = []
        for conferences in self.conference_categories.values():
            all_conferences.extend(conferences)
        all_conferences = list(set(all_conferences))
        
        print(f"\n📋 支持的会议 (支持模糊匹配):")
        for category, conferences in self.conference_categories.items():
            print(f"  {category}: {', '.join(conferences[:3])}{'...' if len(conferences) > 100 else ''}")
        
        # 会议筛选
        selected_input = input("\n请选择会议或领域 (用逗号分隔，留空表示不限制): ").strip()
        selected_conferences = []
        
        if selected_input:
            selections = [item.strip() for item in selected_input.split(',')]
            
            for selection in selections:
                if selection in self.conference_categories:
                    category_conferences = self.conference_categories[selection]
                    selected_conferences.extend(category_conferences)
                    print(f"✅ 已选择 {selection} 领域的所有会议")
                elif selection.upper() in [conf.upper() for conf in all_conferences]:
                    selected_conferences.append(selection.upper())
                    print(f"✅ 已选择会议: {selection.upper()}")
                else:
                    print(f"⚠️ 未找到会议或领域: {selection}")
            
            selected_conferences = list(set(selected_conferences))
            if selected_conferences:
                print(f"🎯 最终选择的会议: {', '.join(selected_conferences)}")
        
        # 时间范围
        print(f"\n📅 发表时间筛选:")
        time_preset = input("使用预设时间范围？(1=最近1年, 2=最近2年, 3=最近5年, 留空=不限制): ").strip()
        start_date = None
        
        if time_preset == "1":
            start_date = datetime.now() - timedelta(days=365)
            print(f"✅ 使用最近1年")
        elif time_preset == "2":
            start_date = datetime.now() - timedelta(days=730)
            print(f"✅ 使用最近2年")
        elif time_preset == "3":
            start_date = datetime.now() - timedelta(days=1825)
            print(f"✅ 使用最近5年")
        else:
            print(f"✅ 不限制时间范围")
        
        # 引用数筛选
        print(f"\n📊 引用数筛选:")
        min_citations_str = input("最小引用数 (留空表示不限制): ").strip()
        min_citations = 0
        if min_citations_str.isdigit():
            min_citations = int(min_citations_str)
            print(f"✅ 最小引用数: {min_citations}")
        
        return SearchFilters(
            start_date=start_date,
            end_date=None,
            conferences=selected_conferences if selected_conferences else None,
            exclude_conferences=None,
            min_citations=min_citations,
            max_citations=None,
            categories=None,
            min_abstract_length=10,
            fuzzy_matching=fuzzy_matching,
            similarity_threshold=similarity_threshold
        )

# 兼容性类
class EnhancedPaperSearcher(EnhancedMultiSourcePaperSearcher):
    """为了向后兼容，保持原有的类名"""
    pass

class PaperSearcher(EnhancedMultiSourcePaperSearcher):
    """为了兼容性，提供原有的接口"""
    
    def search_papers(self, query: str, max_results: int = 10) -> List[Dict]:
        """兼容原有的search_papers接口"""
        filters = SearchFilters(fuzzy_matching=True)
        papers = self.search_papers_multi_source(query, filters)
        return [self._validate_paper_data(paper) for paper in papers]
    
    def search_multiple_queries(self, queries: List[str], max_per_query: int = 5) -> List[Dict]:
        """兼容原有的search_multiple_queries接口"""
        filters = SearchFilters(fuzzy_matching=True)
        global PAPERS_PER_QUERY
        original_papers_per_query = PAPERS_PER_QUERY
        PAPERS_PER_QUERY = max_per_query
        
        try:
            papers = self.search_multiple_queries_enhanced(queries, filters)
            return [self._validate_paper_data(paper) for paper in papers]
        finally:
            PAPERS_PER_QUERY = original_papers_per_query

def demo_multi_source_search():
    """演示多源搜索功能"""
    print("🚀 增强多源论文搜索器演示")
    
    # 初始化搜索器
    searcher = EnhancedMultiSourcePaperSearcher()
    
    # 获取用户搜索偏好
    filters = searcher.get_user_search_preferences()
    
    # 获取搜索查询
    print("\n🔍 请输入搜索查询:")
    base_query = input("搜索关键词: ").strip()
    
    if not base_query:
        base_query = "transformer attention mechanism"
        print(f"使用默认查询: {base_query}")
    
    # 执行搜索
    queries = [base_query]
    results = searcher.search_multiple_queries_enhanced(queries, filters)
    
    # 显示结果
    searcher.display_search_results(results)
    
    return results

if __name__ == "__main__":
    # 运行演示
    results = demo_multi_source_search()