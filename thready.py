from queue import Queue
from threading import Thread, Lock
import urllib.parse
import re
import time
import socket

seen_urls = set(['/'])
lock = Lock()


class Fetcher(Thread):
    def __init__(self, tasks):
        Thread.__init__(self)
        # tasks作为任务队列
        self.tasks = tasks
        self.daemon = True
        self.start()

    def run(self):
        while True:
            url = self.tasks.get()
            print(url)
            sock = socket.socket()
            sock.connect(('localhost', 3000))
            get = 'GET {} HTTP/1.0\nHost: localhost\n\n'.format(url)
            sock.send(get.encode('ascii'))
            response = b''
            chunk = sock.recv(4096)
            while chunk:
                response += chunk
                chunk = sock.recv(4096)
            # 解析页面上的所有链接
            links = self.parse_links(url, response)

            lock.acquire()
            # 得到新链接任务队列与seen_url中
            for link in links.difference(seen_urls):
                self.tasks.put(link)
            seen_urls.update(links)
            lock.release()
            # 通知任务队列这个线程的任务完成了
            self.tasks.task_done()


    def parse_links(self, fetched_url, response):
        if not response:
            print('error: %s' % fetched_url)
            return set()
        if not self._is_html(response):
            return set()

        # 通过html的href属性找到所有的链接
        urls = set(re.findall(r'''(?i)href=["']?([^\s"'<>]+)''', self.body(response)))

        links = set()
        for url in urls:
            # 可能找到的url是相对路径，这时候就需要join一下吗，绝对路径的话就还是返回url
            normalized = urllib.parse.urljoin(fetched_url, url)
            # url的信息会被分段存在parts里
            parts = urllib.parse.urlparse(normalized)
            if parts.scheme not in ('', 'http', 'https'):
                continue
            host, port = urllib.parse.splitport(parts.netloc)
            # 只抓取本网站的，不抓取外链
            if host and host.lower() not in ('localhost'):
                continue
            # 有的页面会通过地址里的#frag后缀在页面内部跳转，这里去掉#frag部分
            defragmented, frag = urllib.parse.urldefrag(parts.path)
            links.add(defragmented)
        return links


    # 提取得到报文的html正文
    def body(self, response):
        body = response.split(b'\r\n\r\n', 1)[1]
        return body.decode('utf-8')


    # 根据header的MIME判断是否为html文件
    def _is_html(self, response):
        head, body = response.split(b'\r\n\r\n', 1)
        headers = dict(h.split(': ') for h in head.decode().split('\r\n')[1:])
        return headers.get('Content-Type', '').startswith('text/html')



class ThreadPool(object):
    def __init__(self, num_thread):
        self.tasks = Queue()
        for _ in range(num_thread):
            Fetcher(self.tasks)

    def add_task(self, url):
        self.tasks.put(url)

    def wait_completion(self):
        self.tasks.join()

if __name__ == '__main__':
    start = time.time()
    pool = ThreadPool(4)
    pool.add_task("/")
    pool.wait_completion()
    print('%s URLs fetched in %s second' % (len(seen_urls), time.time()-start))
