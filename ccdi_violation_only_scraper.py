import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from urllib.parse import urljoin, quote
from datetime import datetime
import os
import re

def get_article_content(url, headers):
    """
    Get the content of an article from its URL
    """
    try:
        print(f"正在获取文章内容...")
        
        # 修改URL格式，确保使用HTTPS
        url = url.replace('http://', 'https://')
        
        # 添加更多请求头，模拟真实浏览器
        full_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Host': 'www.ccdi.gov.cn',
            'Referer': 'https://www.ccdi.gov.cn/',
            'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Cookie': '_gscu_1877571514=82830104l1g3ov14; _gscbrs_1877571514=1'  # 添加基本Cookie
        }
        
        # 合并传入的headers和默认headers
        full_headers.update(headers)
        
        # 添加重试机制
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 发送请求
                session = requests.Session()
                response = session.get(url, headers=full_headers, verify=False, timeout=30)
                response.raise_for_status()
                response.encoding = 'utf-8'
                
                # 保存原始HTML内容
                html_content = response.text
                
                # 检查响应内容是否为空
                if not html_content.strip():
                    print(f"第 {retry_count + 1} 次尝试: 响应内容为空")
                    retry_count += 1
                    time.sleep(5)
                    continue
                
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # 安全地检查标题
                title_tag = soup.title
                title_text = title_tag.string if title_tag else "无标题"
                
                # 检查是否被重定向到登录页或错误页
                if any(keyword in title_text.lower() for keyword in ["登录", "错误", "404", "not found"]):
                    print(f"被重定向到其他页面: {title_text}")
                    retry_count += 1
                    time.sleep(5)
                    continue
                
                # 首先尝试找到文章标题
                article_title = None
                title_candidates = [
                    soup.find('h2', class_='tit'),
                    soup.find('div', class_='tit'),
                    soup.find('h1'),  # 一些页面可能使用h1
                    soup.find('h2')   # 备用：任何h2标签
                ]
                
                for title_candidate in title_candidates:
                    if title_candidate and title_candidate.get_text(strip=True):
                        article_title = title_candidate
                        print(f"找到文章标题: {article_title.get_text(strip=True)}")
                        break
                
                # 查找文章内容 - 尝试多种可能的容器
                content_div = None
                content_candidates = [
                    soup.find('div', class_='content'),
                    soup.find('div', class_='Article_61'),
                    soup.find('div', class_='article-content'),
                    soup.find('div', class_='TRS_Editor'),
                    soup.find('div', class_='article'),
                    # 如果上述都没找到，尝试查找包含大量文本的div
                    max((div for div in soup.find_all('div') if len(div.get_text(strip=True)) > 200),
                        key=lambda x: len(x.get_text(strip=True)), default=None)
                ]
                
                for candidate in content_candidates:
                    if candidate:
                        content_div = candidate
                        print(f"找到文章内容容器: {content_div.get('class', ['unknown'])[0]}")
                        break
                
                if content_div:
                    # 获取所有可能包含内容的标签
                    content_elements = []
                    
                    # 1. 尝试获取所有段落标签
                    paragraphs = content_div.find_all(['p', 'div'], recursive=False)
                    if paragraphs:
                        content_elements.extend(paragraphs)
                    
                    # 2. 如果没有直接的段落，尝试获取所有文本块
                    if not content_elements:
                        text_blocks = [block for block in content_div.stripped_strings
                                     if len(block.strip()) > 20]  # 只保留较长的文本块
                        if text_blocks:
                            content = '\n\n'.join(text_blocks)
                            print(f"使用文本块方法提取内容，共 {len(text_blocks)} 个块")
                            return {'content': content, 'html': html_content}
                    
                    # 处理找到的内容元素
                    if content_elements:
                        content = []
                        for element in content_elements:
                            text = element.get_text(strip=True)
                            if text and len(text) > 20:  # 只保留较长的段落
                                content.append(text)
                        
                        if content:
                            print(f"成功提取文章内容，共 {len(content)} 段")
                            return {'content': '\n\n'.join(content), 'html': html_content}
                    
                    # 如果上述方法都失败，尝试直接获取所有文本
                    text = content_div.get_text(strip=True)
                    if text:
                        print("使用备选方法提取文章内容")
                        # 使用多个分隔符分割文本
                        sentences = []
                        current_sentence = []
                        
                        for char in text:
                            current_sentence.append(char)
                            if char in ['。', '！', '？', '.', '!', '?']:
                                sentence = ''.join(current_sentence).strip()
                                if sentence and len(sentence) > 20:
                                    sentences.append(sentence)
                                current_sentence = []
                        
                        # 处理最后一个句子
                        if current_sentence:
                            sentence = ''.join(current_sentence).strip()
                            if sentence and len(sentence) > 20:
                                sentences.append(sentence)
                        
                        if sentences:
                            return {'content': '\n\n'.join(sentences), 'html': html_content}
                
                print(f"第 {retry_count + 1} 次尝试未找到文章内容")
                retry_count += 1
                time.sleep(5)
                
            except requests.RequestException as e:
                print(f"请求出错 (尝试 {retry_count + 1}/{max_retries}): {str(e)}")
                retry_count += 1
                time.sleep(5)
                continue
            except Exception as e:
                print(f"处理出错 (尝试 {retry_count + 1}/{max_retries}): {str(e)}")
                retry_count += 1
                time.sleep(5)
                continue
        
        print("所有重试都失败，保存HTML内容以供调试")
        debug_filename = f'debug_html_{int(time.time())}.txt'
        with open(debug_filename, 'w', encoding='utf-8') as f:
            f.write(html_content if 'html_content' in locals() else "No response received")
        print(f"已保存HTML内容到: {debug_filename}")
        return None
            
    except Exception as e:
        print(f"获取文章内容时出错: {str(e)}")
        print(f"错误类型: {type(e).__name__}")
        if isinstance(e, requests.RequestException):
            print(f"状态码: {e.response.status_code if hasattr(e, 'response') else 'N/A'}")
        return None

def format_date(date_str):
    """
    Format date string to be suitable for file system
    Remove time component and any special characters
    """
    # Extract just the date part (assuming format like "YYYY-MM-DD HH:MM")
    date_match = re.match(r'(\d{4}-\d{2}-\d{2})', date_str)
    if date_match:
        return date_match.group(1).replace('-', '')
    return date_str.split()[0].replace('-', '')

def save_article_content(title, content, date, html_content=None, base_folder='violation_articles'):
    """
    Save article content to text and HTML files
    Args:
        title: Article title
        content: Article text content
        date: Article date
        html_content: Original HTML content
        base_folder: Base folder for saving files
    """
    try:
        # Create base folder if it doesn't exist
        if not os.path.exists(base_folder):
            os.makedirs(base_folder)
            print(f"创建基础文件夹: {base_folder}")
        
        # Create date folder
        date_folder = os.path.join(base_folder, format_date(date))
        if not os.path.exists(date_folder):
            os.makedirs(date_folder)
            print(f"创建日期文件夹: {date_folder}")
        
        # Clean title for filename
        clean_title = re.sub(r'[\\/*?:"<>|]', '', title)
        
        # Save text content
        txt_filename = os.path.join(date_folder, f"{clean_title}.txt")
        print(f"正在保存文本文件: {txt_filename}")
        
        with open(txt_filename, 'w', encoding='utf-8') as f:
            # 写入标题和日期
            f.write(f"标题：{title}\n")
            f.write(f"日期：{date}\n")
            f.write("="*50 + "\n\n")
            
            # 处理内容，确保没有段落序号
            if isinstance(content, str):
                # 移除可能存在的段落序号（如"1. ", "2. "等）
                cleaned_content = re.sub(r'^\d+\.\s*', '', content)
                # 按换行符分割内容，清理每个段落
                paragraphs = cleaned_content.split('\n')
                cleaned_paragraphs = []
                for para in paragraphs:
                    # 移除每个段落开头可能的序号
                    cleaned_para = re.sub(r'^\d+\.\s*', '', para.strip())
                    if cleaned_para:  # 只添加非空段落
                        cleaned_paragraphs.append(cleaned_para)
                # 用双换行符连接所有段落
                f.write('\n\n'.join(cleaned_paragraphs))
            else:
                f.write("文章内容获取失败")
        
        # Save HTML content if provided
        if html_content:
            # Create HTML folder inside date folder
            html_folder = os.path.join(date_folder, 'html')
            if not os.path.exists(html_folder):
                os.makedirs(html_folder)
                print(f"创建HTML文件夹: {html_folder}")
            
            html_filename = os.path.join(html_folder, f"{clean_title}.html")
            print(f"正在保存HTML文件: {html_filename}")
            
            with open(html_filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return {'txt': txt_filename, 'html': html_filename}
        
        return {'txt': txt_filename}
    
    except Exception as e:
        print(f"保存文章时出错: {str(e)}")
        return None

def scrape_violation_articles(url, params, target_keyword="起违反中央八项规定", delay_between_articles=1):
    """
    Scrape articles containing violations of the eight-point regulation
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Host': 'www.ccdi.gov.cn',
        'Referer': 'https://www.ccdi.gov.cn/',
        'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }
    
    # 确保所有请求都使用相同的headers
    global_headers = headers.copy()  # 创建一个副本用于文章内容获取
    
    try:
        print(f"\n发送POST请求到: {url}")
        print(f"参数: {params}")
        response = requests.post(url, headers=headers, data=params, verify=False)
        response.raise_for_status()
        
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try different methods to find the article list
        article_list = None
        methods = [
            lambda: soup.find('ul', class_='s_0603_list'),
            lambda: soup.find('div', class_='other_center_22').find('ul') if soup.find('div', class_='other_center_22') else None,
            lambda: next((ul for ul in soup.find_all('ul') if ul.find('li') and ul.find('span', class_='time')), None)
        ]
        
        for method in methods:
            article_list = method()
            if article_list:
                break
        
        if not article_list:
            print("\n未找到文章列表！HTML结构可能有变化。")
            return []
        
        articles_data = []
        total_articles = len(article_list.find_all('li'))
        matched_articles = 0
        processed_articles = 0
        failed_articles = 0
        
        print(f"\n找到 {total_articles} 篇文章，开始处理...")
        
        for li in article_list.find_all('li'):
            try:
                a_tag = li.find('a')
                if a_tag:
                    title = a_tag.get_text(strip=True)
                    # Only process articles containing the target keyword
                    if target_keyword in title:
                        matched_articles += 1
                        print(f"\n处理第 {matched_articles} 篇匹配文章: {title}")
                        link = urljoin('https://www.ccdi.gov.cn/', a_tag.get('href', ''))
                        time_span = li.find('span', class_='time')
                        date = time_span.get_text(strip=True) if time_span else ''
                        
                        print(f"获取文章内容: {link}")
                        result = get_article_content(link, global_headers)
                        
                        if result:
                            # Save article content to file
                            saved_files = save_article_content(
                                title, 
                                result['content'], 
                                date,
                                result['html']
                            )
                            
                            if saved_files:  # Only add to articles_data if save was successful
                                processed_articles += 1
                                articles_data.append({
                                    'title': title,
                                    'link': link,
                                    'date': date,
                                    'txt_file': saved_files.get('txt'),
                                    'html_file': saved_files.get('html')
                                })
                                print(f"✓ 成功保存文章到: {saved_files}")
                            else:
                                failed_articles += 1
                                print(f"✗ 保存文章失败: {title}")
                        else:
                            failed_articles += 1
                            print(f"✗ 获取文章内容失败: {title}")
                            
                        # Add a delay between article requests
                        time.sleep(delay_between_articles)
                    else:
                        print(f"跳过不匹配文章: {title}")
                        
            except Exception as e:
                failed_articles += 1
                print(f"处理文章时出错: {str(e)}")
                continue
        
        print(f"\n本页处理统计:")
        print(f"- 总文章数: {total_articles}")
        print(f"- 匹配关键词文章数: {matched_articles}")
        print(f"- 成功处理文章数: {processed_articles}")
        print(f"- 处理失败文章数: {failed_articles}")
        
        return articles_data
        
    except requests.RequestException as e:
        print(f"获取网页失败: {str(e)}")
        return []

def save_to_csv(articles_data, filename=None):
    """
    Save scraped articles metadata to CSV file with timestamp in filename
    """
    if not articles_data:
        print("\nNo data to save!")
        return
        
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'violation_articles_{timestamp}.csv'
    
    df = pd.DataFrame(articles_data)
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"\nData successfully saved to {filename}")
    print(f"Total articles saved: {len(articles_data)}")
    
    # Print summary of findings
    print("\nArticles found by date:")
    date_counts = df['date'].value_counts().sort_index()
    for date, count in date_counts.items():
        print(f"{date}: {count} article(s)")

def scrape_all_pages(base_url, max_pages=10, config=None):
    """
    Scrape multiple pages of search results
    """
    if config is None:
        config = {
            'target_keyword': "起违反中央八项规定",
            'delay_between_pages': 2,
            'delay_between_articles': 1
        }
        
    all_articles = []
    total_pages_processed = 0
    
    for page in range(1, max_pages + 1):
        print(f"\n正在处理第 {page} 页...")
        
        params = {
            'page': str(page),
            'channelid': '298814',
            'searchword': config['target_keyword'],
            'was_custom_expr': f"({config['target_keyword']})",
            'perpage': '10',
            'outlinepage': '10',
            'orderby': '-DocRelTime'
        }
        
        articles = scrape_violation_articles(base_url, params, config['target_keyword'], config['delay_between_articles'])
        
        if not articles:
            print(f"第 {page} 页没有找到更多文章，停止处理")
            break
            
        all_articles.extend(articles)
        total_pages_processed += 1
        
        # Add a delay between pages
        if page < max_pages:  # Don't delay after the last page
            print(f"等待 {config['delay_between_pages']} 秒后处理下一页...")
            time.sleep(config['delay_between_pages'])
    
    print(f"\n总体处理统计:")
    print(f"- 处理页数: {total_pages_processed}")
    print(f"- 成功保存文章总数: {len(all_articles)}")
    
    return all_articles

if __name__ == "__main__":
    # Disable SSL verification warnings
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Configuration
    config = {
        'base_url': "https://www.ccdi.gov.cn/was5/web/search",
        'target_keyword': "起违反中央八项规定",
        'max_pages': 10,
        'output_folder': 'violation_articles',
        'delay_between_pages': 5,
        'delay_between_articles': 3
    }
    
    # Create base folder for articles
    if not os.path.exists(config['output_folder']):
        os.makedirs(config['output_folder'])
    
    # Print configuration
    print("\n当前配置：")
    print(f"- 搜索关键词: {config['target_keyword']}")
    print(f"- 最大页数: {config['max_pages']}")
    print(f"- 输出文件夹: {config['output_folder']}")
    print(f"- 页面间延迟: {config['delay_between_pages']}秒")
    print(f"- 文章间延迟: {config['delay_between_articles']}秒\n")
    
    # Scrape multiple pages
    print("开始抓取违规文章...")
    articles = scrape_all_pages(config['base_url'], config['max_pages'], config)
    
    # Save metadata to CSV with timestamp
    if articles:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'violation_articles_{timestamp}.csv'
        save_to_csv(articles, filename)
        print(f"\n所有文章元数据已保存到: {filename}")
    else:
        print("\n未找到任何符合条件的文章") 

