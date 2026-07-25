


async def a():
    print("a...")
    return 2

def b():
    print("b...")
    return 1

b = b()
print(b)
print(type(b))


a = a()
# print(a)
print(type(a))