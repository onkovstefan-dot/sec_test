def _decorator(fn):
    def _wrapped(*args, **kwargs):
        print("Executing wrapped fn")
        return fn(*args, **kwargs)
    return _wrapped

@_decorator
def my_func(a, b, session=None):
    session = session or "default"
    print("my_func:", session)

my_func(1, 2)
