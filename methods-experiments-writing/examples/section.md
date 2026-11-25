## 方法

1. 读取 CIFAR-10 原始数据并做随机裁剪与水平翻转；输入：原始图像；输出：增强后的训练集。
2. 用 ResNet-18 主干提取特征；输入：增强后的训练集；输出：类别 logits。
3. 以 AdamW 优化交叉熵损失，warmup 3 个 epoch；输入：logits 与标签；输出：模型权重。
4. 在验证集上评估 top-1 准确率；输入：验证集与权重；输出：top-1 指标。

## 实验设置

- 硬件：NVIDIA A100-SXM4-40GB
- 软件：python 3.10.12, torch 2.1.0, cuda 12.1
- 随机种子：42；重复次数：（材料未给出）
- 训练/验证/测试：dataset.split_ratio_train=0.9, dataset.split_ratio_val=0.1

## 参数

| 名称 | 取值 | 单位 | 作用对象 | 来源 |
|---|---|---|---|---|
| model | resnet18 | — | 全局 | config.yaml:1 |
| seed | 42 | — | 全局 | config.yaml:2 |
| train.batch_size | 64 | — | 训练 | config.yaml:4 |
| train.lr | 0.001 | — | 训练 | config.yaml:5 |
| train.epochs | 20 | epochs | 训练 | config.yaml:6 |
| train.weight_decay | 0.0001 | — | 训练 | config.yaml:7 |
| opt.name | adamw | — | 优化器 | config.yaml:12 |
| opt.warmup_epochs | 3 | epochs | 优化器 | config.yaml:10 |
| dataset.name | CIFAR-10 | — | 数据 | config.yaml:12 |
| dataset.n_train | 50000 | — | 数据 | config.yaml:13 |
| dataset.split_ratio_train | 0.9 | — | 数据 | config.yaml:14 |
| dataset.split_ratio_val | 0.1 | — | 数据 | config.yaml:15 |
| preprocess | random crop and horizontal flip | — | 全局 | config.yaml:16 |

## 数据集

- 名称：CIFAR-10；版本：（未给出）；规模：50000
- 预处理：random crop and horizontal flip；划分：split_ratio_train=0.9, split_ratio_val=0.1

## 对照实验

- 基线 vanilla resnet18（版本 未给出，同预算：未说明）
- 基线 mixup resnet18（版本 未给出，同预算：未说明）

## 可复现性

- 代码版本：git commit: 4f7c2ab
- 环境：python 3.10.12, torch 2.1.0, cuda 12.1
- 数据获取：/data/cifar10

## 限制

- 正文数值与配置不一致：train.lr（失效场景：按正文 0.01 复现会得到与记录不同的结果；需作者确认）
- 正文数值无材料来源：87.3%（失效场景：该数值可能来自未提供的材料，复现时无法核对；需作者确认）
- 数据集版本未在材料中给出（失效场景：换版本后划分与指标会变化，复现结果不可比；需作者确认）
- 基线未说明是否同预算（失效场景：不同训练预算下的对比结论不成立；需作者确认）
