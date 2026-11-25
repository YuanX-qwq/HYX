# 双语对照：ml.pdf

case_id=demo-arxiv-1605.01735 status=success coverage=100.0% terms=37

> 每个段落以 pid 与原文页码锚定；未译段落标注 `[未译]`。

## P0002 · p1 · title

**EN** Machine learning phases of matter

**ZH** 物质的机器学习相

## P0005 · p1 · abstract

**EN** Neural networks can be used to identify phases and phase transitions in condensed matter systems via supervised machine learning. Readily programmable through modern software libraries, we show that a standard feed-forward neural network can be trained to detect multiple types of order parameter directly from raw state configurations sampled with Monte Carlo. In addition, they can detect highly non-trivial states such as Coulomb phases, and if modified to a convolutional neural network, topological phases with no conventional order parameter. We show that this classification occurs within the neural network without knowledge of the Hamiltonian or even the general locality of interactions. These results demonstrate the power of machine learning as a basic research tool in the field of condensed matter and statistical physics.

**ZH** 神经网络可用于通过监督式机器学习识别凝聚态体系中的相与相变。借助现代软件库即可方便地编程实现，我们证明：一个标准的前馈神经网络经过训练，能够直接从蒙特卡洛采样的原始状态构型中识别出多种类型的序参量。此外，它还能识别诸如库仑相这类高度非平庸的态；若改为卷积神经网络，则可识别没有常规序参量的拓扑相。我们表明，这种分类发生在神经网络内部，无需知晓哈密顿量，甚至无需知晓相互作用的一般局域性。这些结果展示了机器学习作为凝聚态与统计物理领域基础研究工具的威力。

## P0007 · p2 · body

**EN** Condensed matter physics is the study of the collective behavior of massively complex assemblies of electrons, nuclei, magnetic moments, atoms or qubits [1]. This complexity is reflected in the size of the classical or quantum state space, which grows exponentially with the number of particles. This exponential growth is reminiscent of the "curse of dimensionality" commonly encountered in machine learning. That is, a target function to be learned requires an amount of training data that grows exponentially in the dimension (e.g. the number of image features). Despite this curse, the machine learning community has developed a number of techniques with remarkable abilities to recognize, classify, and characterize complex sets of data. In light of this success, it is natural to ask whether such techniques could be applied to the arena of condensed-matter physics, particularly in cases where the microscopic Hamiltonian contains strong interactions, where numerical simulations are typically employed in the study of phases and phase transitions [2, 3]. We demonstrate that modern machine learning architectures, such as fully-connected and convolutional neural networks [4], can provide a complementary approach to identifying phases and phase transitions in a variety of systems in condensed matter physics. The training of neural networks on data sets obtained by Monte Carlo sampling provides a particularly powerful and simple framework for the supervised learning of phases and phase boundaries in physical models, and can be easily built from readily-available tools such as Theano [5] or TensorFlow [6] libraries.

**ZH** 凝聚态物理研究的是由电子、原子核、磁矩、原子或量子比特构成的大规模复杂集合体的集体行为[1]。这种复杂性体现在经典或量子状态空间的规模上：状态空间随粒子数呈指数增长。这种指数增长让人联想到机器学习中常见的“维度灾难”。也就是说，一个待学习的目标函数所需的训练数据量随维度（例如图像特征的数量）呈指数增长。尽管存在这一灾难，机器学习界已发展出若干技术，具备识别、分类与刻画复杂数据集的非凡能力。鉴于这些成功，人们自然会问：这类技术能否应用于凝聚态物理领域，尤其是在微观哈密顿量包含强相互作用、而人们通常借助数值模拟研究相与相变的情形[2, 3]？我们证明，现代机器学习架构（例如全连接神经网络与卷积神经网络[4]）可为识别凝聚态物理中各类体系的相与相变提供一条互补途径。利用蒙特卡洛采样得到的数据集训练神经网络，为物理模型中相与相边界的监督学习提供了一个格外强大而简单的框架，并且可以借助 Theano[5] 或 TensorFlow[6] 等现成工具库轻松搭建。

## P0008 · p2 · body

**EN** Conventionally, the study of phases in condensed matter systems is performed with the help of tools that have been carefully designed to elucidate the underlying physical structures of various states. Among the most powerful are Monte Carlo simulations, which consist of two steps: a stochastic importance sampling over state space, and the evaluation of estimators for physical quantities calculated from these samples [3]. These estimators are constructed based on a variety of physical impetuses; e.g. the ready availability of an analogous experimental measure like a specific heat; or, the encoding of some more abstract theoretical device, like an order parameter [1]. However, unique and technologically important states of matter may not be straightforwardly identified with standard estimators. Indeed, for some highly-coveted phases such as topologically-ordered states [1, 7], positive identification may require prohibitively expensive (and experimentally challenging [8]) measures such as the entanglement entropy [9, 10].

**ZH** 传统上，对凝聚态体系中相的研究，是借助为阐明各种态的底层物理结构而精心设计的工具来完成的。其中最有力的工具是蒙特卡洛模拟，它包含两步：在状态空间上做随机重要性采样，以及由这些样本计算物理量的估计量[3]。这些估计量依据多种物理动因构造，例如可类比比热这类现成的实验测量；又如可编码序参量这类更抽象的理论装置[1]。然而，具有独特技术重要性的物态可能无法用标准估计量直接识别。的确，对于某些备受追捧的相，例如拓扑有序态[1, 7]，要正面识别它们，可能需要诸如纠缠熵[9, 10]之类昂贵得难以承受（且在实验上颇具挑战[8]）的测量手段。

## P0009 · p2 · body

**EN** Machine learning, already explored as a tool in condensed matter and materials research [12-17], provides an alternate paradigm to the above approach. The ability of modern machine learning techniques to classify, identify, or interpret massive data sets like images, videos, genome sequences, internet traffic statistics, natural language recordings, etc. foreshadows their suitability to provide physicists with similar analyses on the exponentially large data sets embodied in the state space of condensed matter systems. We first demonstrate this on the prototypical example of the square-lattice ferromagnetic Ising model, ⟨ij⟩σz i σz j. We set the energy scale J = 1; the Ising variables σz

**ZH** 机器学习早已作为凝聚态与材料研究的工具被探索[12-17]，它为上述途径提供了一种替代范式。现代机器学习技术能够对图像、视频、基因组序列、互联网流量统计、自然语言录音等海量数据集进行分类、识别或解读，这预示着它们同样适合为物理学家完成对凝聚态体系状态空间所蕴含的指数级大数据集的类似分析。我们首先在正方晶格铁磁伊辛模型这一原型例子上演示这一点，⟨ij⟩σz i σz j。我们取能量标度为 J = 1；伊辛变量 σz

## P0019 · p3 · caption

**EN** FIG. 1. Machine learning the ferromagnetic Ising model. (A) The trained neural network learns representations of the low- and high-temperature Ising states. The average output layer (B) and accuracy (C) over the test sets vs. temperature. (D) Toy model of a neural network for the Ising model. (E) The average output layer and accuracy of the toy model are displayed in (E) and (F), respectively. The orange lines signal Tc of the model in the thermodynamic limit, Tc/J = √ 2/ ln 1 + [11].

**ZH** 图 1. 用机器学习研究铁磁伊辛模型。(A) 训练后的神经网络学习到低温与高温伊辛态的表示。测试集上的平均输出层 (B) 与准确率 (C) 随温度的变化。(D) 用于伊辛模型的神经网络玩具模型。(E) 玩具模型的平均输出层与准确率分别显示于 (E) 和 (F)。橙色线标示热力学极限下该模型的 Tc，即 Tc/J = √ 2/ ln 1 + [11]。

## P0021 · p4 · body

**EN** H = −J P i = ±1 so that for N lattice sites, the state space is of size 2N. Standard Monte Carlo techniques can efficiently provide samples of configurations for any temperature T, weighted by the Boltzmann distribution. The existence of a well-understood phase transition at temperature Tc [11], between a high-temperature paramagnetic phase and a low-temperature ferromagnetic phase, allows us the opportunity to attempt to classify the two different types of configurations without the use of Monte Carlo estimators (e.g. the magnetization). Instead, we construct a fully connected feed-forward neural network, implemented with TensorFlow [6], to perform supervised learning directly on the raw configurations sampled by a Monte Carlo simulation (see Figure 1). The neural network is composed of an input layer with values determined by the spin configurations, 100-unit hidden layer of sigmoid neurons, and an analogous output layer. We use a cross-entropy cost function supplemented with an L2 regularization term to prevent overfitting. The neural network is trained using the Adam method for stochastic optimization [18]. As Illustrated in Figure 1(A) through (C), when trained on a broad range of temperatures above and below Tc, the neural network is able to correctly classify 94% of uncorrelated data provided in a test set, at the same temperatures as in the training set, for a system of N = L2 = 102 spins. The classification accuracy improves as the system size is increased (as high as 99% for L = 40), as inferred from Figure 1(C), indicating that this training/testing paradigm is capable of systematically narrowing in on the true thermodynamic value of Tc in a way analogous to the direct measurement of the magnetization in a conventional Monte Carlo simulation. In fact, due to the simplicity of the underlying order parameter (a bulk polarization of Ising spins below Tc), one can understand the training of the network through a simple toy model involving a hidden layer of only three analytically "trained" perceptrons, representing the possible combinations of high and low-temperature magnetic states exclusively based on their magnetization.

**ZH** H = −J P i = ±1，因此对 N 个格点，状态空间大小为 2N。标准蒙特卡洛技术能够高效地给出任意温度 T 下的构型样本，并按玻尔兹曼分布加权。在温度 Tc 处存在一个已被充分理解的相变[11]：高温顺磁相与低温铁磁相之间发生转变，这使我们有机会尝试在不使用蒙特卡洛估计量（例如磁化强度）的情况下对这两类构型进行分类。作为替代，我们构造一个全连接的前馈神经网络（用 TensorFlow[6] 实现），直接对蒙特卡洛模拟采样得到的原始构型进行监督学习（见图 1）。该神经网络由输入层（取值由自旋构型决定）、含 100 个单元的 S 型神经元隐藏层，以及一个与之类似的输出层构成。我们采用交叉熵代价函数，并附加 L2 正则化项以防止过拟合。网络使用 Adam 随机优化方法训练[18]。如图 1(A) 至 (C) 所示，当在 Tc 上下较宽的温度范围内训练后，对于 N = L2 = 102 个自旋的体系，该网络能够以 94% 的正确率对测试集中提供的、与训练集温度相同的无关联数据进行分类。如图 1(C) 所示，分类准确率随体系尺寸增大而提高（当 L = 40 时高达 99%），这表明该训练/测试范式能够以类似于常规蒙特卡洛模拟中直接测量磁化强度的方式，系统地逼近 Tc 的真实热力学值。事实上，由于底层序参量十分简单（Tc 以下伊辛自旋的整体极化），人们可以通过一个简单的玩具模型来理解该网络的训练：该模型仅包含三个经解析“训练”的感知机所构成的隐藏层，它们完全依据磁化强度来表示高温与低温磁态的可能组合。

## P0022 · p4 · body

**EN** As illustrated in Figure 1(D) through (F), it performs the classification task with remarkably high accuracy. We em- phasize that the toy model has no a priori knowledge of the critical temperature. Further details about the toy model, as well as a low-dimensional visualization of the training data to gain intuition for how these neural networks operate, are discussed in the supplementary materials. Similar results and success rates occur if the model is modified to have ⟨ij⟩σz i σz anti-ferromagnetic couplings, H = J P j, illustrating that the neural network is not only useful in identifying a global spin polarization, but an order parameter with a more complicated ordering wave vector ( here q = (π/a, π/a), where a is the lattice spacing).

**ZH** 如图 1(D) 至 (F) 所示，它以极高的准确率完成分类任务。我们要强调，该玩具模型并不先验地知道临界温度。关于该玩具模型的更多细节，以及为直观理解这些神经网络如何工作而对训练数据所做的低维可视化，将在补充材料中讨论。若把模型改为具有 ⟨ij⟩σz i σz 反铁磁耦合，H = J P j，也会得到类似的结果与成功率，这说明该神经网络不仅能用于识别整体的自旋极化，还能识别具有更复杂有序波矢的序参量（此处 q = (π/a, π/a)，其中 a 为晶格常数）。

## P0024 · p5 · body

**EN** Clearly, such a framework does not provide the same quantitive understanding as a direct Monte Carlo measurement of the order parameter, which sits on a solid bedrock of decades of statistical mechanics theory. However, the power of neural networks lies in their ability to generalize to tasks beyond their original design. For example, what if one was presented with a data set of Ising configurations from an unknown Hamiltonian, where the lattice structure (and therefore its Tc) is not known? We illustrate this scenario by taking our above feed-forward neural network, already trained on configurations for the square-lattice ferromagnetic Ising model, and feed it a test set produced by Monte Carlo simulations of the triangular lattice ferromagnetic Ising Hamiltonian. The network has no information about the Hamiltonian, the lattice structure, or even the general locality of interactions. In Figure 2 we present the output layer neurons averaged over the test set as a function of temperature for L = 30. We estimate the critical temperature based on the crossing point of the low- and high-temperature outputs to be Tc/J = 3.63581, which is close to the exact thermodynamic Tc/J = 4/ ln 3 ≈ 3.640957 [19] - a discrepancy easily attributed to finite-size effects.

**ZH** 显然，这样的框架并不能提供与直接蒙特卡洛测量序参量同等的定量理解——后者建立在数十年统计力学理论的坚实基石之上。然而，神经网络的力量在于其泛化到原始设计之外任务的能力。例如，如果面对的是一个来自未知哈密顿量的伊辛构型数据集，而晶格结构（因而其 Tc）未知，情况会怎样？我们通过以下情景来说明：取上述已在正方晶格铁磁伊辛模型构型上训练好的前馈神经网络，向它输入由三角晶格铁磁伊辛哈密顿量的蒙特卡洛模拟产生的测试集。该网络对哈密顿量、晶格结构，甚至相互作用的一般局域性都一无所知。在图 2 中，我们给出 L = 30 时输出层神经元在测试集上的平均值随温度的变化。我们根据低温与高温输出的交点估计临界温度，得到 Tc/J = 3.63581，接近精确的热力学值 Tc/J = 4/ ln 3 ≈ 3.640957[19]——这一偏差很容易归因于有限尺寸效应。

## P0025 · p5 · body

**EN** Further, the same strategy can be repeated, using instead our toy neural network. Again, without any knowledge of the critical temperatures on the square or triangular lattices, we estimate Tc/J = 3.63403, differing from the true thermodynamic critical Tc by less than 1%.

**ZH** 此外，改用我们的玩具神经网络，同样的策略可以重复。同样地，在完全不知道正方晶格或三角晶格临界温度的情况下，我们估计出 Tc/J = 3.63403，与真实热力学临界值 Tc 相差小于 1%。

## P0026 · p5 · body

**EN** We turn to the application of such techniques to problems of greater interest in modern condensed matter, such as disordered or topological phases, where no conventional order parameter exists. Coulomb phases, for example, are states of frustrated lattice models where local energetic constraints lead to extensively degenerate classical ground states, which are highly-correlated "spin liquids" without a bulk magnetization or other local order parameter.

**ZH** 我们把这类技术转向现代凝聚态中更有意义的问题，例如不存在常规序参量的无序相或拓扑相。以库仑相为例，它是阻挫晶格模型中的一类态：局域能量约束导致大量简并的经典基态，这些基态是高度关联的“自旋液体”，既没有体磁化强度，也没有其他局域序参量。

## P0027 · p5 · body

**EN** v Q2 We consider a two-dimensional square ice Hamiltonian given by H = J P v where the i∈v σz charge at vertex v is Qv = P i , and the Ising variables located in the lattice bonds as shown in Figure 3. In a conventional condensed-matter approach, the ground states and the high-temperature states are distinguished by their spin-spin correlation functions: power-law decay in the Coulomb phase at T = 0, and exponential decay at high temperature. Instead we use supervised learning, feeding raw Monte Carlo configurations to train a fullyconnected neural network (Figure 1(A)) to distinguish ground states from high-temperature states. Figure 3(A) and Figure 3(B) display high- and low-temperature snapshots of the configurations used in the training of the model. For a square ice system with N = 2 × 16 × 16 spins, we find that a standard fully-connected neural network with 100 hidden units successfully distinguishes the states with a 99% accuracy. The network does so solely based on spin configurations, with no information about the underlying lattice - a feat difficult for the human eye, even if supplemented with a layout of the underlying Hamiltonian locality.

**ZH** v Q2 我们考虑一个二维方冰哈密顿量，H = J P v，其中顶点 v 处的 i∈v σz 电荷为 Qv = P i，伊辛变量位于如图 3 所示的晶格键上。在常规凝聚态方法中，基态与高温态通过自旋-自旋关联函数加以区分：在 T = 0 的库仑相中呈幂律衰减，而在高温下呈指数衰减。作为替代，我们采用监督学习，将原始蒙特卡洛构型输入一个全连接神经网络（图 1(A)），以区分基态与高温态。图 3(A) 与图 3(B) 展示了用于模型训练的高温与低温构型快照。对于 N = 2 × 16 × 16 个自旋的方冰体系，我们发现一个含 100 个隐藏单元的标准全连接神经网络能以 99% 的准确率成功区分这些态。该网络仅依据自旋构型完成判断，完全不知道底层晶格——即使辅以底层哈密顿量局域性的布局图，这一任务对人眼而言也十分困难。

## P0031 · p6 · caption

**EN** FIG. 2. Detecting the critical temperature of the triangular Ising model through the crossing of the values of the output layer vs T. The orange line signals the triangular Ising model Tc/J = 4/ ln 3, while the blue dashed line represents our estimate Tc/J = 3.63581.

**ZH** 图 2. 通过输出层取值随 T 变化的交点来检测三角伊辛模型的临界温度。橙色线标示三角伊辛模型的 Tc/J = 4/ ln 3，蓝色虚线表示我们的估计值 Tc/J = 3.63581。

## P0032 · p6 · body

**EN** These results indicate that the learning capabilities of neural networks go beyond the simple ability to encode order parameters, extending to the detection of subtle differences in higher-order correlations functions. As a final demonstration of this, we examine an Ising lattice gauge theory, one of the most prototypical examples of a topological phase of matter i∈p σz [7, 20]. The Hamiltonian is given by H = −J P Q i where the Ising spins live on p the bonds of a two-dimensional square lattice with plaquettes p, as shown in the inset of Figure 3(C). The ground state is again a degenerate manifold [7, 21] (Figure 3(C)), with exponentially-decaying spin-spin correlations that makes it much more difficult to distinguish from the high temperature phase.

**ZH** 这些结果表明，神经网络的学习能力超越了编码序参量这一简单能力，还扩展到检测更高阶关联函数中的细微差异。作为最后一项演示，我们考察一个伊辛格点规范理论，它是拓扑相物质最具代表性的例子之一，i∈p σz[7, 20]。其哈密顿量由 H = −J P Q i 给出，其中伊辛自旋位于二维正方晶格的键上，p 为面元，如图 3(C) 的插图所示。基态同样是一个简并流形[7, 21]（图 3(C)），其自旋-自旋关联呈指数衰减，这使其与高温相的区分困难得多。

## P0036 · p7 · caption

**EN** FIG. 3. Typical configurations of square ice and Ising gauge models. (A) A high-temperature state. (B) A ground state of the square ice Hamiltonian. (C) A ground state configuration of the Ising lattice gauge theory. The vertices and plaquettes defining the square ice and Ising gauge theory Hamiltonians are shown in the insets of (B) and (C).

**ZH** 图 3. 方冰模型与伊辛规范模型的典型构型。(A) 高温态。(B) 方冰哈密顿量的一个基态。(C) 伊辛格点规范理论的一个基态构型。定义方冰与伊辛规范理论哈密顿量的顶点与面元分别示于 (B) 与 (C) 的插图中。

## P0037 · p7 · body

**EN** Just as in the square ice model, we have made an attempt to use the neural network in Figure 1(A) to classify the high- and low- temperature states in the Ising gauge theory. A straightforward implementation of supervised training fails to classify a test set containing samples of the two states to an accuracy over 50% - equivalent to simply guessing. Such failures typically occur because the neural network overfits to the training set. To overcome this difficulty we consider a convolutional neural network (CNN) [4, 22] which readily takes advantage of the two-dimensional structure of the input configurations, as well as the translational invariance of the model. The CNN in Figure 4 is detailed in the supplementary materials. We optimize the CNN using Monte Carlo configurations drawn from the partition function of the Ising gauge theory at T = 0 and T = ∞. Using this setting, the CNN successfully discriminates high-temperature from ground states with an accuracy of 100% on a test set with 1 × 104 configurations, in spite of the lack of an order parameter or qualitative differences in the spin-spin correlations. Through the generation of new test sets that violate an extensive fraction of the local energetic constraints of the theory, we conclude that the discriminative power of the CNN relies on the detection of these satisfied constraints. Furthermore, test sets with defects that retain most local constraints but disrupt non-local features, like the extended closed-loop gas picture or the associated topological degeneracy [7], indicate that local constraints are the only features that the CNN relies on for classification of the ground state. In view of these observations, we construct a simplified analytical toy model of our original CNN designed to explicitly exploit local constraints in the classification task. Such a model discriminates high-temperature from ground states with an accuracy of 100%. Details of the behavior of the CNN with various test sets, as well as the details of the analytical model, are contained in the supplementary material.

**ZH** 与方冰模型一样，我们尝试用图 1(A) 中的神经网络对伊辛规范理论中的高温态与低温态进行分类。直接实施监督训练无法把包含这两种态样本的测试集分类到 50% 以上的准确率——这等同于随机猜测。这类失败通常是因为神经网络对训练集过拟合。为克服这一困难，我们考虑使用卷积神经网络（CNN）[4, 22]，它能够方便地利用输入构型的二维结构以及模型的平移不变性。图 4 中的 CNN 在补充材料中有详细说明。我们使用从伊辛规范理论在 T = 0 与 T = ∞ 时的配分函数抽取的蒙特卡洛构型来优化该 CNN。在此设置下，尽管不存在序参量、自旋-自旋关联也没有定性差异，该 CNN 仍能在含 1 × 104 个构型的测试集上以 100% 的准确率成功区分高温态与基态。通过生成违反该理论相当一部分局域能量约束的新测试集，我们得出结论：CNN 的判别能力依赖于对这些被满足的约束的检测。此外，带有缺陷的测试集保留了大部分局域约束、却破坏了非局域特征（例如延展的闭环气体图像或相关的拓扑简并[7]），这类测试集表明局域约束是 CNN 用于基态分类的唯一依据。鉴于这些观察，我们为原始 CNN 构造了一个简化的解析玩具模型，旨在分类任务中显式利用局域约束。该模型以 100% 的准确率区分高温态与基态。CNN 在不同测试集下行为的细节以及解析模型的细节均见补充材料。

## P0041 · p8 · caption

**EN** FIG. 4. Illustrating the convolutional neural network. The first hidden layer convolves 64 2 × 2 filters with the spin configuration on each sublattice, followed by rectified linear units (ReLu). The outcome is followed by fully-connected layer with 64 units and a softmax output layer. The green line represents the sliding of the maps across the configuration.

**ZH** 图 4. 卷积神经网络示意。第一个隐藏层用 64 个 2 × 2 的滤波器与每个子晶格上的自旋构型做卷积，随后经过修正线性单元（ReLU）。其输出接一个含 64 个单元的全连接层以及一个 softmax 输出层。绿线表示特征图在构型上的滑动。

## P0042 · p8 · body

**EN** We have shown that neural network technology, developed for engineering applications such as computer vision and natural language processing, can be used to encode phases of matter and discriminate phase transitions in correlated many-body systems. In particular, we have argued that neural networks encode information about conventional ordered phases by learning the order parameter of the phase, without knowledge of the energy or locality conditions of Hamiltonian. Furthermore, we have shown that neural networks can encode basic information about the ground states of unconventional disordered models, such as square ice model and the Ising lattice gauge theory, where they learn local constraints satisfied by the spin configurations in the absence of an order parameter. These results indicate that neural networks have the potential to faithfully represent ground state wave functions. For instance, ground states of the toric code [1, 7] can be represented by convolutional neural networks akin to the one in Figure 4 (see the supplementary materials for details). We thus anticipate adoption to the field of quantum technology [23], such as quantum error correction protocols and quantum state tomography [24]. The ability of machine learning algorithms to generalize to situations beyond their original design anticipates future applications such as the detection of phases and phase transitions in models vexed with the Monte Carlo sign problem [3], as well as in experiments with single-site resolution capabilities such as the modern quantum gas microscopes [25, 26]. As in all other areas of "big data", we expect the rapid adoption of machine learning techniques as a basic research tool in condensed matter and statistical physics in the near future.

**ZH** 我们已经表明，为计算机视觉与自然语言处理等工程应用而发展起来的神经网络技术，可用于编码物相并判别关联多体体系中的相变。特别地，我们论证了：神经网络通过习得物相的序参量来编码常规有序相的信息，而无需知道哈密顿量的能量或局域性条件。此外，我们还表明，神经网络能够编码非常规无序模型基态的基本信息，例如方冰模型与伊辛格点规范理论——在这些体系中，神经网络在不存在序参量的情况下学习自旋构型所满足的局域约束。这些结果表明，神经网络有潜力忠实表示基态波函数。例如，环面码[1, 7]的基态可由类似图 4 的卷积神经网络表示（细节见补充材料）。因此，我们预期这些方法会被量子技术领域[23]所采纳，例如用于量子纠错协议与量子态层析[24]。机器学习算法泛化到原始设计之外情境的能力，预示着未来的应用，例如检测受蒙特卡洛符号问题[3]困扰的模型中的相与相变，以及在具备单格点分辨能力的实验（如现代量子气体显微镜[25, 26]）中的应用。与“大数据”的所有其他领域一样，我们预计机器学习技术将在不久的将来迅速成为凝聚态与统计物理中的基础研究工具。

## P0044 · p9 · body

**EN** Acknowledgments. We would like to thank Ganapathy Baskaran, Claudio Castelnovo, Anushya Chandran, Lauren E. Hayward Sierens, Bohdan Kulchytskyy, David Schwab, Miles Stoudenmire, Giacomo Torlai, Guifre Vidal, and Yuan Wan for discussions and encouragement. We thank Adrian Del Maestro for a careful reading of the manuscript. This research was supported by NSERC of Canada, the Perimeter Institute for Theoretical Physics, the John Templeton Foundation, and the Shared Hierarchical Academic Research Computing Network (SHARCNET). R.G.M. acknowledges support from a Canada Research Chair. Research at Perimeter Institute is supported through Industry Canada and by the Province of Ontario through the Ministry of Research & Innovation.

**ZH** 致谢。我们感谢 Ganapathy Baskaran、Claudio Castelnovo、Anushya Chandran、Lauren E. Hayward Sierens、Bohdan Kulchytskyy、David Schwab、Miles Stoudenmire、Giacomo Torlai、Guifre Vidal 与 Yuan Wan 的讨论与鼓励。我们感谢 Adrian Del Maestro 仔细阅读书稿。本研究得到加拿大 NSERC、圆周理论物理研究所、John Templeton 基金会以及共享分层学术研究计算网络（SHARCNET）的支持。R.G.M. 感谢加拿大研究主席项目的支持。圆周理论物理研究所的研究由加拿大工业部以及安大略省研究与创新部通过其资助。

## P0045 · p9 · heading · Appendix A: Details of the toy model

**EN** Appendix A: Details of the toy model

**ZH** 附录 A：玩具模型的细节

## P0046 · p9 · body · Appendix A: Details of the toy model

**EN** The analytical model encodes the low- and high-temperature phases of the Ising model through their magnetization. The hidden layer contains 3 perceptrons (a neuron with a Heaviside step nonlinearity); the first two perceptrons activate when the input states are mostly polarized, while the third one activate if the states are polarized up or unpolarized. Notice that the third neuron can also be choosen to activate if the states are polarized down or unpolarized. The resulting outcomes are recombined in the output layer and produce the desired classification of the state. The hidden layer is parametrized through a weight matrix

**ZH** 该解析模型通过磁化强度来编码伊辛模型的低温相与高温相。隐藏层包含 3 个感知机（一种带 Heaviside 阶跃非线性的神经元）；前两个感知机在输入态大部分极化时激活，第三个则在态向上极化或未极化时激活。注意，第三个神经元也可以选择为在态向下极化或未极化时激活。所得结果在输出层重新组合，给出对状态的所需分类。隐藏层由权重矩阵参数化

## P0057 · p10 · caption · Appendix A: Details of the toy model

**EN** FIG. 5. Hidden layer arguments as a function of the magnetization of the Ising state m(x). (A) Hidden layer arguments for our toy model. (B) and (C) show the arguments for a neural network with 3 sigmoid neurons before and after training, respectively.

**ZH** 图 5. 隐藏层自变量作为伊辛态磁化强度 m(x) 的函数。(A) 我们玩具模型的隐藏层自变量。(B) 与 (C) 分别显示含 3 个 S 型神经元的神经网络在训练前与训练后的自变量。

## P0061 · p10 · body · Appendix A: Details of the toy model

**EN** 1 where 0 < ϵ < 1 is the only free parameter of the model. The arguments of the three hidden layer neurons, in terms of the weight matrix, bias vector, and a particular Ising configuration x = (σ1σ2, ..., σN)T, are given by

**ZH** 1 其中 0 < ϵ < 1 是模型唯一的自由参数。三个隐藏层神经元（在给定权重矩阵、偏置向量与某一特定伊辛构型 x = (σ1σ2, ..., σN)T 时）的自变量为

## P0063 · p10 · heading · PN

**EN** PN

**ZH** P N

## P0064 · p10 · footnote · PN

**EN** 1 where m(x) = σi is the magnetization of the Ising configuration. In Figure 5(A) we

**ZH** 1 其中 m(x) = σi 是伊辛构型的磁化强度。在图 5(A) 中我们

## P0065 · p10 · body · PN

**EN** N i=1 display the components of the Wx + b vector as a function of the magnetization of the Ising state m(x). The first and second neuron activate when the state is predominantly polarized, i.e., when m(x) > ϵ or m(x) < −ϵ. The third neuron activates if the state has a magnetization m(x) > −ϵ, which means that, in the limit where 0 < ϵ ≪ 1, it activates when the state is either polarized or unpolarized. The parameter ϵ is thus a threshold value of the magnetization that helps deciding whether the state is considered polarized or not.

**ZH** N i=1 给出 Wx + b 向量的各分量随伊辛态磁化强度 m(x) 的变化。第一个与第二个神经元在态以某种极化为主时激活，即当 m(x) > ϵ 或 m(x) < −ϵ 时。第三个神经元在态具有磁化强度 m(x) > −ϵ 时激活；这意味着在 0 < ϵ ≪ 1 的极限下，只要态是极化的或未极化的，它都会激活。因此参数 ϵ 是磁化强度的一个阈值，用于帮助判定该态是否被视为极化。

## P0067 · p11 · body · PN

**EN** The output layer is parametrized through a weight matrix and bias vector given by     −1  2 1 0 W2 = , and b2 = (A3) , −2 −2 1 0 where these arbitrary choices ensure that the ordered, low-T output neuron OLow-T = 1 is active when either the spins polarize mostly ↑ or ↓. On the other hand, when the ↑∥ 0 neuron is active but the ↑ is not, then the high-temperature output neuron OHigh-T = 1, symbolizing a high-temperature state.

**ZH** 输出层由权重矩阵与偏置向量参数化，二者为 −1 2 1 0 W2 = , 以及 b2 = (A3) , −2 −2 1 0 这些任意选定的取值确保：当自旋主要朝 ↑ 或朝 ↓ 极化时，有序的低温输出神经元 OLow-T = 1 处于激活状态。另一方面，当 ↑∥ 0 神经元激活而 ↑ 神经元不激活时，高温输出神经元 OHigh-T = 1，表示高温态。

## P0068 · p11 · body · PN

**EN** To illustrate what the effects of the training on the parameters W and b are, we consider the numerical training of a fully-connected neural network with only 3 neurons using the same setup and training/test data used in our ferromagnetic model (Figure 1) for the L = 30 system. In Figure 5(B) we display the argument W0x + b0 of the input layer at training iteration t = 0 for configurations x in the test set as a function of the magnetization of the configurations m(x). The weights have been randomly initialized at t = 0 from a normal distribution with zero mean and unit standard deviation. As the training proceeds, the parameters adjust such that the components of the vector Wtx + bt approximately become linear functions of the magnetization m(x), as shown in Figure 5(C), in agreement with the assumptions of our toy model. These results clearly support our claim about the neural network's ability encode and learn the magnetization in the hidden layer.

**ZH** 为说明训练对参数 W 与 b 的影响，我们考虑对一个仅含 3 个神经元的全连接神经网络做数值训练，所用设置与训练/测试数据与铁磁模型（图 1）中 L = 30 体系相同。在图 5(B) 中，我们给出训练迭代 t = 0 时输入层的自变量 W0x + b0 随测试集中构型 x 的磁化强度 m(x) 的变化。权重在 t = 0 时由零均值、单位标准差的普通分布随机初始化。随着训练进行，参数不断调整，使向量 Wtx + bt 的各分量近似成为磁化强度 m(x) 的线性函数，如图 5(C) 所示，这与我们玩具模型的假设一致。这些结果清楚地支持了我们关于神经网络能够在隐藏层中编码并学习磁化强度的论断。

## P0069 · p11 · heading · Appendix B: Visualizing the action of a neural network on the Ising ferromagnet

**EN** Appendix B: Visualizing the action of a neural network on the Ising ferromagnet

**ZH** 附录 B：可视化神经网络在伊辛铁磁体上的作用

## P0070 · p11 · body · Appendix B: Visualizing the action of a neural network on the Ising ferromagnet

**EN** A strategy to gain intuition for how these neural networks operate is to produce a low-dimensional visualization of data used in the training. We consider the t-distributed stochastic neighbor embedding (t-SNE) technique [27] where high-dimensional data is embedded in two or three dimensions so that data points close to each other in the original space are also positioned close to each other in the embedded low-dimensional space. Figure 6 displays a t-SNE visualization of the Ising configurations used the training of our ferromagnetic model. The two low-temperature blue regions correspond to the two ordered states with spins polarized either up or down. The high-temperature red region identifies the paramagnetic state. The resulting neural networks, which are functions defined over the high-dimensional state space, become trained so that the low-temperature output neuron takes a high value in the cool region (and vice versa), crossing over to a low value as the system is warmed through the orange hyperplane. This allows the classification of a state in terms of the neuron values.

**ZH** 要直观理解这些神经网络如何运作，一种策略是对训练所用数据做低维可视化。我们采用 t 分布随机邻域嵌入（t-SNE）技术[27]，它把高维数据嵌入二维或三维空间，使原始空间中彼此接近的数据点在嵌入的低维空间中也彼此接近。图 6 展示了用于训练铁磁模型的伊辛构型的 t-SNE 可视化。两个低温蓝色区域对应自旋分别向上或向下极化的两个有序态。高温红色区域标示顺磁态。由此得到的神经网络是定义在高维状态空间上的函数，训练后低温输出神经元在低温区域取高值（反之亦然），当体系经由橙色超平面升温时则过渡到低值。这使得可以依据神经元取值对状态进行分类。

## P0073 · p12 · caption · Appendix B: Visualizing the action of a neural network on the Ising ferromagnet

**EN** FIG. 6. Two-dimensional t-SNE visualization of the training set used in the Ising model for L = 30 colored according to temperature. The orange line represents a hyperplane separating the low- from high-temperatures states.

**ZH** 图 6. 用于伊辛模型 L = 30 训练集的二维 t-SNE 可视化，按温度着色。橙色线表示分隔低温态与高温态的超平面。

## P0074 · p12 · heading · Appendix C: Details of the convolutional neural network of the Ising lattice gauge theory

**EN** Appendix C: Details of the convolutional neural network of the Ising lattice gauge theory

**ZH** 附录 C：伊辛格点规范理论卷积神经网络的细节

## P0075 · p12 · body · Appendix C: Details of the convolutional neural network of the Ising lattice gauge theory

**EN** The exact architecture of the convolutional neural network (CNN) [4], schematically described in Figure 4, is as follows. The input layer is a two-dimensional Ising spin configuration with N = 16 × 16 × 2 spins, where σi = ±1. The first hidden layer convolves 64 2 × 2 filters on each of the two sublattices of the model with a unit stride, no padding, with periodic boundary conditions, followed by rectified linear unit (ReLu). The final hidden layer is a fully-connected layer with 64 ReLu units, while the output is a softmax layer with two outputs (correponding to T = 0 and T = ∞ states). To prevent overfitting, we apply a dropout regularization in the fully-connected layer [28]. Our model has been implemented using TensorFlow [6].

**ZH** 图 4 所示卷积神经网络（CNN）[4] 的确切架构如下。输入层是含 N = 16 × 16 × 2 个自旋的二维伊辛自旋构型，其中 σi = ±1。第一个隐藏层在模型的两个子晶格上分别用 64 个 2 × 2 的滤波器做卷积，步长为 1、无填充、周期边界条件，随后通过修正线性单元（ReLU）。最后的隐藏层是含 64 个 ReLU 单元的全连接层，而输出是含两个输出（分别对应 T = 0 与 T = ∞ 态）的 softmax 层。为防止过拟合，我们在全连接层中施加 dropout 正则化[28]。我们的模型用 TensorFlow[6] 实现。

## P0077 · p13 · body · Appendix C: Details of the convolutional neural network of the Ising lattice gauge theory

**EN** Since our CCN correctly classifies T = 0 and T = ∞ states with 100% accuracy, we would like to scrutinize the origin of its discriminiative power by asking whether it discerns the states by the presence (or absence) of the local Hamiltonian constraints or the extended closed-loop structure. Our strategy consists in the construction of new test sets with modified low temperature states, as detailed below. First, we consider transformations that do not destroy the topological order [21] of the T = 0 state but change the local constraints of the original Ising lattice gauge theory. As shown in the configurations in Figure 7(A) and (B), we consider transformations where a spin is flipped every m = 2 (A) (m = 8 (B)) plaquettes. The positions of the flipped spins are marked with red crosses. After optimizing the CNN using the original training set, the neural network classifies most of the transformed T = 0 states as high-temperature ones, resulting in an overall test accuracy of 50% and 55% for m = 2 and m = 8, respectively. This reveals that the neural network relies on the presence of satisfied local constraints of the original Ising lattice gauge theory, and not on the topological order of the state, in deciding whether a state is considered low or high temperature. Second, we consider a new test set where the T = 0 states retain most local constraints but disrupt non-local features like the extended closed-loop structure. We consider dividing the original states into 4 pieces as shown in Figure 7(C) and then reshuffling the 4 pieces among different states, subsequently stitching them to form new "low" temperature configurations. The new configurations will contain defects along the dashed lines in Figure 7(C), thus disrupting the extended closed-loop picture, but preserving the local constraints everywhere else in the configuration. We find that the trained CNN recognizes such states as ground states with high confidence, suggesting that the CNN does not use the extended closed-loop structure and indicating that local constraints are the only features that the CNN relies on for classification of the ground state.

**ZH** 由于我们的 CCN 能以 100% 的准确率正确分类 T = 0 与 T = ∞ 态，我们希望细究其判别能力的来源：它究竟依据局域哈密顿量约束的有无，还是依据延展的闭环结构来辨别这些态？我们的策略是构造带有修改后低温态的新测试集，具体如下。首先，我们考虑不破坏 T = 0 态拓扑序[21]、但会改变原始伊辛格点规范理论局域约束的变换。如图 7(A) 与 (B) 中的构型所示，我们考虑每隔 m = 2（A）与 m = 8（B）个面元翻转一个自旋的变换，被翻转自旋的位置以红色叉号标出。在用原始训练集优化 CNN 后，该神经网络把大多数变换后的 T = 0 态归类为高温态，总体测试准确率在 m = 2 与 m = 8 时分别为 50% 与 55%。这揭示出：网络在判定一个态应属低温还是高温时，依赖的是原始伊辛格点规范理论中被满足的局域约束是否存在，而非该态的拓扑序。其次，我们考虑一个新的测试集：其中 T = 0 态保留大部分局域约束，但破坏诸如延展闭环结构这类非局域特征。我们按图 7(C) 所示把原始态切成 4 块，再在不同态之间重新打乱这 4 块，随后拼接成新的“低温”构型。新构型会沿图 7(C) 中的虚线带有缺陷，从而破坏延展闭环图像，但在构型的其他各处仍保留局域约束。我们发现，训练后的 CNN 以高置信度把这类态识别为基态，这表明 CNN 并未使用延展闭环结构，也说明局域约束是 CNN 用于基态分类的唯一依据。

## P0078 · p13 · body · Appendix C: Details of the convolutional neural network of the Ising lattice gauge theory

**EN** In view of the conclusion above, we now present a toy model that uses a streamlined ver-sion of our original CNN constructed to explicitly detect satisfied energetic local constraints. The convolutional layer contains 16 2×2 filters per sublattice with unit stride in both directions and periodic boundary conditions. The convolutional layer is fully connected to two perceptron neurons in the output layer, as described below. A schematic representation of the toy CNN is presented in Figure 8. The values of the filters Wyxsf are presented in Table C, where x and y represent the spatial indices of the convolution, and s and f label the sublattice and the filter, respectively. The purpose of the filters is to individually process each plaquette in the spin configuration and determine whether its energetic constraints are satisfied or not. The Ising gauge theory contains 16 different spin configurations per plaquette, of which 8 satisfy the energetic constraints of the Hamiltonian. The first group of 16 filters Wyxsf (f = 1 thorugh f = 8, left blue column in Table C) detect satisfied plaquettes, while the remaining 16 (f = 9 through f = 16, right red column in Table C) detect unsatisfied plaquettes. The bias of the convolutional layer is a 16-dimensional vector given by bc = −(2+δ) (1 · · · 1)T, where 0 < δ ≪ 1 is a small parameter. The outcome of the convolutional layer consists of 16 two-dimensional arrays of size L × L processed through perceptrons. Here the total number of spins in the configuration is N = 2 × L × L, where

**ZH** 鉴于上述结论，我们现在给出一个玩具模型，它使用原始 CNN 的简化版本，旨在显式检测被满足的能量局域约束。其卷积层在每个子晶格上含 16 个 2×2 滤波器，两个方向步长均为 1，并采用周期边界条件。该卷积层与输出层中的两个感知机神经元全连接，具体如下。图 8 给出该玩具 CNN 的示意图。滤波器 Wyxsf 的取值列于表 C，其中 x 与 y 表示卷积的空间指标，s 与 f 分别标记子晶格与滤波器。滤波器的作用是逐一处理自旋构型中的每个面元，并判定其能量约束是否被满足。伊辛规范理论中每个面元有 16 种不同的自旋构型，其中 8 种满足哈密顿量的能量约束。第一组 16 个滤波器 Wyxsf（f = 1 至 f = 8，表 C 左蓝列）检测被满足的面元，其余 16 个（f = 9 至 f = 16，表 C 右红列）检测未被满足的面元。卷积层的偏置是一个 16 维向量，由 bc = −(2+δ) (1 · · · 1)T 给出，其中 0 < δ ≪ 1 是小参数。卷积层的输出由 16 个经感知机处理的 L × L 二维阵列构成。此处构型中的自旋总数为 N = 2 × L × L，其中

## P0081 · p14 · caption · Appendix C: Details of the convolutional neural network of the Ising lattice gauge theory

**EN** FIG. 7. Investigating the source of discriminative power of the convolutional neural network. New test sets with sublattice rotations where the local constrains are such that 1/2 spins per plaquette (A) and 1/8 spins per plaquette (B) are flipped. The red crossess symbolize the flipped spins. (C) Cuts/stitches (yellow dashed lines) performed on the ground state configurations in order to produce a new test set from mixing the 4 resulting pieces among different ground states.

**ZH** 图 7. 探究卷积神经网络判别能力的来源。新的测试集带有子晶格旋转，其中局域约束为每个面元有 1/2 个自旋（A）与 1/8 个自旋（B）被翻转。红色叉号表示被翻转的自旋。(C) 为生成新测试集而对基态构型所做的切割/拼接（黄色虚线），即把得到的 4 块在不同基态之间混合。

## P0084 · p14 · caption · Appendix C: Details of the convolutional neural network of the Ising lattice gauge theory

**EN** FIG. 8. Toy model of a convolutional neural network to classify states of the Ising gauge theory.

**ZH** 图 8. 用于分类伊辛规范理论态的卷积神经网络玩具模型。

## P0102 · p15 · caption · Appendix C: Details of the convolutional neural network of the Ising lattice gauge theory

**EN** TABLE I. Specifying the tensor Wyxsf filters in the CNN. y and x specify the spatial indices of the filter, while s and f specify the sublattice and the filter, respectively.

**ZH** 表 I. CNN 中张量 Wyxsf 滤波器的设定。y 与 x 指定滤波器的空间指标，s 与 f 分别指定子晶格与滤波器。

## P0103 · p15 · body · Appendix C: Details of the convolutional neural network of the Ising lattice gauge theory

**EN** L is the linear size of the system. The outcome of the convolutional layer is reshaped into a 16 × L2-dimensional vector such that the first 8L2 entries correspond to the outcome of the first group of filters (f = 1 thorugh f = 8) while the remaining 8L2 correspond to the last group of filters (f = 9 through f = 16). The output layer, which is fully connected to the the convolutional layer, contains two perceptron neurons denoted by O0 and O∞ for zero- and high-temperature states, respectively. It is parametrized through a weight matrix and a bias vector given by 8L2 terms   8L2 terms   0 z }| { −L2 + L − 1 . . . − L2 + L − 1 z }| { 1 . . . 1 Wo = and bo = (C1) ,     0

**ZH** L 是体系的线度。卷积层的输出被重塑为 16 × L2 维向量，使前 8L2 个分量对应第一组滤波器（f = 1 至 f = 8）的输出，其余 8L2 个分量对应最后一组滤波器（f = 9 至 f = 16）。与卷积层全连接的输出层包含两个感知机神经元，分别记为 O0 与 O∞，对应零温态与高温态。它由权重矩阵与偏置向量参数化，二者为 8L2 项 8L2 项 0 z }| { −L2 + L − 1 . . . − L2 + L − 1 z }| { 1 . . . 1 Wo = 以及 bo = (C1) , 0

## P0104 · p15 · body · Appendix C: Details of the convolutional neural network of the Ising lattice gauge theory

**EN** L2 − L + 1 . . . L2 − L + 1

**ZH** L2 − L + 1 … L2 − L + 1

## P0106 · p15 · body · Appendix C: Details of the convolutional neural network of the Ising lattice gauge theory

**EN** These choices ensure that whenever an unsatisfied plaquette is encountered by the convo- lutional layer, the zero-temperature neuron is O0 = 0 and the high-temperature O∞ = 1, while only if all energetic constraints are satisfied O0 = 1 and O∞ = 0, thus allowing the classification of the states. When used on our test sets, the model performs the classification task with a 100% accuracy, which means that all the high temperature states in the test set contain least one unsatisfied plaquette. Note that the classification error for this task is expected to be exponentially small in the volume of the system, since at infinte temperature the ground states appear with exponentially small probability. Having distilled the model's basic ingredients, we proceed to train an analogue model numerically starting from random weights and biases Wyxsf, Wo, bc, and bo. Further, we replace the perceptron nonlinearities by ReLu units and a softmax output layer to enable a reliable numerical training. After the training, the model performs the classification task with a 100% accuracy on the test sets, as expected.

**ZH** 这些选择确保：每当卷积层遇到未被满足的面元时，零温神经元取 O0 = 0、高温神经元取 O∞ = 1；而只有当所有能量约束都被满足时，才有 O0 = 1 与 O∞ = 0，从而实现对状态的分类。在我们的测试集上使用时，该模型以 100% 的准确率完成分类任务，这意味着测试集中的所有高温态都至少含有一个未被满足的面元。注意，该任务的分类误差预期随体系体积呈指数减小，因为在无限温度下基态出现的概率是指数小的。在提炼出模型的基本要素之后，我们接着从一个随机的权重与偏置 Wyxsf、Wo、bc、bo 出发，对该模型的一个类似版本做数值训练。此外，我们把感知机非线性替换为 ReLU 单元并采用 softmax 输出层，以实现可靠的数值训练。训练之后，模型如预期地在测试集上以 100% 的准确率完成分类任务。

## P0108 · p16 · body · Appendix C: Details of the convolutional neural network of the Ising lattice gauge theory

**EN** As a consequence of the classification scheme provided by the analytical toy model, we observe that the values of the zero-temperature neuron O0 behave exactly like the am-plitudes of one of the ground states of the toric code written in the σz basis [7].

**ZH** 作为解析玩具模型所给出的分类方案的推论，我们观察到：零温神经元 O0 的取值行为，与环面码的某一基态在 σz 基下写出的振幅完全一致[7]。

## P0109 · p16 · body · Appendix C: Details of the convolutional neural network of the Ising lattice gauge theory

**EN** The ground state described by O0 is a linear combination of all 4 ground states with well More precisely, such a state can be written as |ψtoric⟩ = defined parity on the torus. P σz1,...,σzN O0(σz1...σzN)|σz1...σzN⟩, where the spin configurations σzi = ±1, and O0(σz1...σzN) corresponds to the value of O0 after a feed-forward pass of the neural network for a given a input configuration σz 1, ..., σz N. Our model bears resemblance with the construction of the ground state of the toric code in terms of projected entangled pair states in that local tensors project out states containing plaquettes with odd parity [29]. These observations suggest that convolutional neural networks have the potential to represent ground states with topological order.

**ZH** 由 O0 描述的基态是所有 4 个在环面上具有确定宇称的基态的线性组合。更准确地说，该态可写为 |ψtoric⟩ = P σz1,...,σzN O0(σz1...σzN)|σz1...σzN⟩，其中自旋构型 σzi = ±1，而 O0(σz1...σzN) 对应给定输入构型 σz 1, ..., σz N 经神经网络前馈后 O0 的取值。我们的模型与用投影纠缠对态构造环面码基态的做法相似：其中的局域张量会把含有奇宇称面元的状态投影掉[29]。这些观察表明，卷积神经网络有潜力表示具有拓扑序的基态。

