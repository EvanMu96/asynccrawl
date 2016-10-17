from selectors import *
import socket
import re
import urllib.parse
import time
import asyncio

class Future(object):
    def __init__(self):
        self.result = None
        self._callbacks = []

    def add_done_callback(self, fn):
        self._callbacks.append(fn)

    def result(self):
        return self.result

    def set_result(self, result):
        self.result = result
        for fn in self._callbacks:
            for fn in self._callbacks:
                fn(self)

    # 统一yield和yield from
    def __iter__(self):
        yield self
        return self.result


class Task(object):
    def __init__(self, coro):
        # 协程
        self.coro = coro
        # 创建并初始化一个为None的Future对象
        f = Future()
        f.set_result(None)
        # 步进一次（发送一次信息）
        # 在厨师话的时候发送一个None是为了达到第一个个yield的位置,也是为了下一次的步进
        self.step(f)

    def step(self, future):
        try:
            # 向协程发送消息并得到下一个从协程那yield到的Future对象
            next_future = self.coro.send(future.result)
        except StopIteration:
            return

        next_future.add_done_callback(self.step)


class Fetcher(object):
    def fetch(self):
        self.sock = socket.socket()
        self.sock.setblocking(False)
        try:
            self.sock.connect(('localhost', 3000))
        except BlockingIOError:
            pass

        f = Future()

        def on_connect():
            # 连接建立后通过set_result协程继续从yield的地方往下运行
            f.set_result(None)

