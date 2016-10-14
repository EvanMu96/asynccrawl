from selectors import *
import socket
import time
import re
import urllib.parse

urls_todo = set(['/'])
seen_url = set(['/'])
# 追加一个可以看最高并发的变量

concurrency_achieved = 0
selector = DefaultSelector()
stopped = False


# 将回调函数封装在Fetcher类里
class Fetcher(object):
    def __init__(self, url):
        self.response = b''
        self.url = url
        self.sock = None

    # 实现fetch函数，绑定connected
    def fetch(self):
        global concurrency_achieved
        concurrency_achieved = max(concurrency_achieved, len(urls_todo))

        self.sock = socket.socket()
        self.sock.setblocking(False)
        try:
            self.sock.connect(('localhost', 3000))
        except BlockingIOError:
            pass

        selector.register(self.sock.fileno(), EVENT_WRITE, self.connected)

    def connected(self, key, mask):
        # print('connected!')
        # 接触该socket上的所有绑定
        selector.unregister(key.fd)
        get = 'GET {} HTTP/1.0\nHost: localhost\n\n'.format(self.url)

        self.sock.send(get.encode('ascii'))
        # 建立连接后绑定读取相应的回调函数
        selector.register(key.fd, EVENT_READ, self.read_response)

    def read_response(self, key, mask):
        global stopped

        chunk = self.sock.recv(4096) # 4k chunk size
        if chunk:
            self.response += chunk
        else:

            selector.unregister(key.fd) # Done reading
            links = self.parse_links()
            for link in links.difference(seen_url):
                urls_todo.add(link)
                Fetcher(link).fetch()

            seen_url.update(links)
            urls_todo.remove(self.url)

            if not urls_todo:
                stopped = True
            print(self.url)

    def parse_links(self):
        if not self.response:
            print('error: %s' % self.url)
            return set()
        if not self._is_html():
            return set()

        # 通过html的href属性找到所有的链接
        urls = set(re.findall(r'''(?i)href=["']?([^\s"'<>]+)''', self.body()))

        links = set()
        for url in urls:
            # 可能找到的url是相对路径，这时候就需要join一下吗，绝对路径的话就还是返回url
            normalized = urllib.parse.urljoin(self.url, url)
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
    def body(self):
        body = self.response.split(b'\r\n\r\n', 1)[1]
        return body.decode('utf-8')

    # 根据header的MIME判断是否为html文件
    def _is_html(self):
        head, body = self.response.split(b'\r\n\r\n', 1)
        headers = dict(h.split(': ') for h in head.decode().split('\r\n')[1:])
        return headers.get('Content-Type', '').startswith('text/html')





# 建立事件循环
# 当stopped时停止
if __name__ == '__main__':
    start = time.time()
    fetcher = Fetcher('/')
    fetcher.fetch()
    while not stopped:
        events = selector.select()
        for event_key, event_mask in events:
            callback = event_key.data
            callback(event_key, event_mask)
    print('{} URLs fetched in {:.1f} second, achieved concurrency = {}'.format(len(seen_url), time.time()-start, concurrency_achieved))