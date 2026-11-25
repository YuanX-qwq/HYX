[step 1] 读取 CIFAR-10 原始数据并做随机裁剪与水平翻转；输入：原始图像；输出：增强后的训练集
[step 2] 用 ResNet-18 主干提取特征；输入：增强后的训练集；输出：类别 logits
[step 3] 以 AdamW 优化交叉熵损失，warmup 3 个 epoch；输入：logits 与标签；输出：模型权重
[step 4] 在验证集上评估 top-1 准确率；输入：验证集与权重；输出：top-1 指标
