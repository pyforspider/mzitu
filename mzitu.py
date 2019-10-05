import asyncio
import os
import aiofiles
import aiohttp
from aiomultiprocess import Pool
from bs4 import BeautifulSoup


start_url = 'https://www.mzitu.com'
waiting_urls = []
sem = asyncio.Semaphore(450)


# 请求一个url, 返回 response
async def fetch(url, session=None, referer=None):
	headers = {
		'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_3) AppleWebKit/537.36 (HTML, like Gecko) '
		'Chrome/65.0.3325.162 Safari/537.36',
		'Referer': referer
	}
	try:
		resp = await session.get(url, headers=headers)
		return resp
	except Exception as e:
		print("获取链接{}时检测到异常：{}".format(url, e))


# 一开始的待爬取url队列为空， 需要从 start_url解析出url
async def init_urls(url, session):
	resp = await fetch(url, session, url)
	html = await resp.text()
	global waiting_urls
	soup = BeautifulSoup(html, "html.parser")
	waiting_urls = [li.find("a").attrs["href"] for li in soup.find_all("div")[2].find_all("li")]
	return waiting_urls


# 解析每个系列的图片数量
async def get_pic_num(url):
	async with aiohttp.ClientSession() as session:
		while True:
			try:
				resp = await fetch(url, session, url)
				html = await resp.read()
				soup = BeautifulSoup(html, "html.parser")
				pic_num = int(soup.find(lambda tag: tag.name == 'a' and '下一页»' in tag.text).find_previous_sibling().text)
			except AttributeError:
				await asyncio.sleep(1)
				continue
			else:
				break
		return pic_num


# 解析每个系列的图片链接,保存到文件
async def article_handle(url, num):
	async with sem:
		async with aiohttp.ClientSession() as session:
			while True:
				try:
					resp = await fetch(url, session, url)
					html = await resp.read()
					soup = BeautifulSoup(html, "html.parser")
					target_pic_link = soup.find_all("div")[2].find_all("div")[3].find("img").attrs["src"]
				except IndexError or AttributeError:
					await asyncio.sleep(1)
					continue
				else:
					break

			res = await fetch(target_pic_link, session, url)
			content = await res.read()
			file_path = "img" + os.path.sep + soup.find_all("div")[2].find_all("div")[3].find("img").attrs["alt"]
			if not os.path.exists(file_path):
				os.makedirs(file_path)
			file_path = file_path + os.path.sep + '{}.jpg'.format(num)
			async with aiofiles.open(file_path, "wb") as fb:
				print('Already save Pic file {} NO:{}'.format(file_path, num))
				await fb.write(content)


# 提交目标url中图片链接的协程 -> 解析并储存到文件
async def consumer():
	async with Pool() as pool:
		num_lis = await pool.map(get_pic_num, waiting_urls)
	for link_num in zip(waiting_urls, num_lis):
		url, num = link_num
		for i in range(1, num+1):
			link = url + "/{}".format(i)
			asyncio.ensure_future(article_handle(link, i))


# 爬虫 主逻辑
async def main():
	async with aiohttp.ClientSession() as session:
		await init_urls(start_url, session)
	asyncio.ensure_future(consumer())


if __name__ == '__main__':
	loop = asyncio.get_event_loop()
	task = asyncio.ensure_future(main())
	loop.run_forever()
