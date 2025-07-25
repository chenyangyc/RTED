```python
  def test_request_httprepr(self):
        class HttpRequest:
            def __init__(self):
                self.url = 'http://example.com'
                self.method = 123
                self.headers = None
                self.body = b''
        http_request = HttpRequest()
        request_httprepr(http_request)
```