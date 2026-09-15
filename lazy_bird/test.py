
async def wait():
    sleep(1)
    print("hello world")

async def my_func():
    await wait()
    print("my_func done")