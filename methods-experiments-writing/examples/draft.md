# 方法与实验（草稿）

我们在 CIFAR-10 上训练 ResNet-18，batch size 为 64，学习率 0.01，共 20 个 epoch。
优化器使用 AdamW，warmup 3 个 epoch，weight decay 为 0.0001。
训练集与验证集按 9:1 划分，随机种子为 42。
最终模型在验证集上的 top-1 准确率达到 87.3%。
与 vanilla resnet18 相比我们的方法更好。
