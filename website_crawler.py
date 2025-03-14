from bs4 import BeautifulSoup
import logging
import time
import random
from playwright.async_api import async_playwright
import asyncio

from util.common_util import CommonUtil
from util.llm_util import LLMUtil
from util.oss_util import OSSUtil

llm = LLMUtil()
oss = OSSUtil()

# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(filename)s - %(funcName)s - %(lineno)d - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

global_agent_headers = [
    "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:30.0) Gecko/20100101 Firefox/30.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.75.14 (KHTML, like Gecko) Version/7.0.3 Safari/537.75.14",
    "Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; Win64; x64; Trident/6.0)",
    'Mozilla/5.0 (Windows; U; Windows NT 5.1; it; rv:1.8.1.11) Gecko/20071127 Firefox/2.0.0.11',
    'Opera/9.25 (Windows NT 5.1; U; en)',
    'Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 1.1.4322; .NET CLR 2.0.50727)',
    'Mozilla/5.0 (compatible; Konqueror/3.5; Linux) KHTML/3.5.5 (like Gecko) (Kubuntu)',
    'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.8.0.12) Gecko/20070731 Ubuntu/dapper-security Firefox/1.5.0.12',
    'Lynx/2.8.5rel.1 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/1.2.9',
    "Mozilla/5.0 (X11; Linux i686) AppleWebKit/535.7 (KHTML, like Gecko) Ubuntu/11.04 Chromium/16.0.912.77 Chrome/16.0.912.77 Safari/535.7",
    "Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:10.0) Gecko/20100101 Firefox/10.0 "
]

class WebsitCrawler:
    def __init__(self):
        self.browser = None
        self.playwright = None
        self.max_retries = 1
        self.retry_delay = 10

    async def ensure_browser(self):
        """Ensure browser is running and connected"""
        try:
            if not self.playwright:
                self.playwright = await async_playwright().start()

            # Check if browser needs to be (re)created
            if not self.browser or not self.browser.is_connected():
                if self.browser:
                    try:
                        await self.browser.close()
                    except:
                        pass
                
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-software-rasterizer',
                        '--disable-setuid-sandbox'
                    ],
                    ignore_default_args=['--enable-automation'],
                    handle_sigint=False,
                    handle_sigterm=False,
                    handle_sighup=False
                )
                logger.info("Browser (re)initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to ensure browser: {e}")
            return False

    async def get_new_context(self):
        """Create new browser context with retry logic"""
        for attempt in range(self.max_retries):
            try:
                if not await self.ensure_browser():
                    raise Exception("Browser initialization failed")
                
                context = await self.browser.new_context(
                    user_agent=random.choice(global_agent_headers),
                    ignore_https_errors=True
                )
                return context
            except Exception as e:
                logger.error(f"Failed to create context (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
                raise

    async def wait_for_page_stability(self, page, timeout=30000):
        """Wait for page to become stable"""
        try:
            # Wait for network to be idle
            await page.wait_for_load_state('networkidle', timeout=timeout)
            # Wait a bit more to ensure dynamic content is loaded
            await asyncio.sleep(2)
            # Wait for any visible loading indicators to disappear (customize selectors as needed)
            await page.wait_for_selector('.loading', state='hidden', timeout=5000).catch(lambda _: None)
            return True
        except Exception as e:
            logger.warning(f"Page stability check warning: {e}")
            return False

    async def get_page_content_safely(self, page, max_attempts=3):
        """Safely get page content with retries"""
        for attempt in range(max_attempts):
            try:
                # Wait for page to stabilize
                await self.wait_for_page_stability(page)
                
                # Check if page is still navigating
                if await page.evaluate('() => document.readyState') != 'complete':
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(2)
                        continue
                
                # Get content
                content = await page.content()
                return content
            except Exception as e:
                logger.warning(f"Content retrieval attempt {attempt + 1} failed: {e}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2)
                    continue
                raise

    # 爬取指定URL网页内容
    async def scrape_website(self, url, tags, languages):
        # 开始爬虫处理
        start_time = int(time.time())
        context = None
        page = None
        
        try:
            # Set overall timeout for the entire operation
            async with asyncio.timeout(110):  # 110 seconds timeout
                logger.info("正在处理：" + url)
                if not url.startswith('http://') and not url.startswith('https://'):
                    url = 'https://' + url

                # Get new context with retry logic
                for attempt in range(self.max_retries):
                    try:
                        context = await self.get_new_context()
                        page = await context.new_page()

                        # 设置页面视口大小
                        width = 1920
                        height = 1080
                        await page.set_viewport_size({"width": width, "height": height})

                        # Navigate to page with better error handling
                        try:
                            await page.goto(url, timeout=100000)
                            # Wait for initial load
                            await page.wait_for_load_state('domcontentloaded', timeout=30000)
                        except Exception as e:
                            logger.warning(f'页面加载可能不完整，继续尝试处理：{e}')

                        # Get page content safely
                        try:
                            origin_content = await self.get_page_content_safely(page)
                        except Exception as e:
                            logger.error(f"无法获取页面内容: {e}")
                            raise

                        soup = BeautifulSoup(origin_content, 'html.parser')

                        # 通过标签名提取内容
                        title = soup.title.string.strip() if soup.title else ''

                        # 根据url提取域名生成name
                        name = CommonUtil.get_name_by_url(url)

                        # 获取网页描述
                        description = ''
                        meta_description = soup.find('meta', attrs={'name': 'description'})
                        if meta_description:
                            description = meta_description['content'].strip()

                        if not description:
                            meta_description = soup.find('meta', attrs={'property': 'og:description'})
                            description = meta_description['content'].strip() if meta_description else ''

                        logger.info(f"url:{url}, title:{title},description:{description}")

                        # Wait for page to stabilize before screenshot
                        await self.wait_for_page_stability(page)

                        # 生成网站截图
                        image_key = oss.get_default_file_key(url)
                        screenshot_path = './' + url.replace("https://", "").replace("http://", "").replace("/", "").replace(".", "-") + '.png'
                        await page.screenshot(path=screenshot_path, clip={"x": 0, "y": 0, "width": width, "height": height})

                        # 上传图片，返回图片地址
                        screenshot_key = oss.upload_file_to_s3(screenshot_path, image_key)

                        # 生成缩略图
                        thumnbail_key = oss.generate_thumbnail_image(url, image_key)

                        # 抓取整个网页内容
                        content = soup.get_text()

                        # 使用llm工具处理content
                        detail = llm.process_detail(content)

                        # Close page and context after successful scraping
                        await page.close()
                        page = None
                        await context.close()
                        context = None

                        # 如果tags为非空数组，则使用llm工具处理tags
                        processed_tags = None
                        if tags and detail:
                            processed_tags = llm.process_tags('tag_list is:' + ','.join(tags) + '. content is: ' + detail)

                        # 循环languages数组， 使用llm工具生成各种语言
                        processed_languages = []
                        if languages:
                            for language in languages:
                                logger.info("正在处理" + url + "站点，生成" + language + "语言")
                                processed_title = llm.process_language(language, title)
                                processed_description = llm.process_language(language, description)
                                processed_detail = llm.process_language(language, detail)
                                processed_languages.append({'language': language, 'title': processed_title,
                                                         'description': processed_description, 'detail': processed_detail})

                        logger.info(url + "站点处理成功")
                        return {
                            'name': name,
                            'url': url,
                            'title': title,
                            'description': description,
                            'detail': detail,
                            'screenshot_data': screenshot_key,
                            'screenshot_thumbnail_data': thumnbail_key,
                            'tags': processed_tags,
                            'languages': processed_languages,
                        }

                    except Exception as e:
                        logger.error(f"Attempt {attempt + 1} failed: {e}")
                        if page:
                            await page.close()
                            page = None
                        if context:
                            await context.close()
                            context = None
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(self.retry_delay)
                            continue
                        raise

        except asyncio.TimeoutError:
            logger.error(f"处理{url}超时，超过110秒")
            return None
        except Exception as e:
            logger.error(f"处理{url}站点异常，错误信息: {str(e)}")
            return None
        finally:
            # Clean up resources
            if page:
                try:
                    await page.close()
                except Exception as e:
                    logger.error(f"关闭page异常: {str(e)}")
            if context:
                try:
                    await context.close()
                except Exception as e:
                    logger.error(f"关闭context异常: {str(e)}")
            
            # 计算程序执行时间
            execution_time = int(time.time()) - start_time
            logger.info(f"处理{url}用时：{execution_time}秒")

    async def close(self):
        """Clean up all resources"""
        try:
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")