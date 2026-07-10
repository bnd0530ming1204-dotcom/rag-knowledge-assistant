
import torch
print(torch.cuda.is_available())  # 如果输出 True，说明成功认出显卡！
print(torch.version.cuda)