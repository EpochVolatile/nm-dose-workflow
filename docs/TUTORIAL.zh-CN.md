# 中文教程：从建模到积分剂量

## 1. 先确认在哪里操作

| 提示符/窗口 | 执行内容 |
|---|---|
| Windows PowerShell | `Install-Stack.ps1`、`Run-Workflow.ps1`、`View-Results.ps1` |
| WSL 的 Bash | `bash scripts/...`、Linux 路径和环境变量 |
| 3D Slicer 的 Python Console | `slicer`、MRML 节点和扩展逻辑 |

PowerShell 进入 Linux：

```powershell
wsl -d AlmaLinux-9.6 -u root
```

本教程下文的 `REPO`、`OUT` 是 **Bash 变量**。`REPO` 应替换为实际仓库路径；可以在 Windows 下载后用 `wslpath` 查询，不需要复制算例到 Git 仓库。

```bash
REPO=/path/to/nm-dose-workflow
OUT=$HOME/sim-data/nm-dose-workflow/my-first-run
mkdir -p "$OUT/logs"
cd "$REPO"
```

## 2. 怎样建模

默认模型由 `nm/phantom.py` 生成：

- 图像形状：x/y/z = 32/32/8，体素边长 4 mm。
- 几何：半径 48 mm、全高 32 mm 的水圆柱。
- 热点：球心 LPS `(16,-12,2)` mm，半径 12 mm，中心采样的体素活度为背景的 8 倍。
- 活度：参考时刻总和为 1,000,000 Bq，图像单位是 **Bq/voxel**。
- 分区：0=空气，1=水背景，2=热点。热点替代背景标签，不重复计数。

```bash
bash scripts/python.sh nm/phantom.py --out "$OUT/phantom"
```

修改模型时，首先修改 `phantom.py` 中的网格、热点和活度；随后同步修改 `gate_acquire.py`、`gate_dose.py` 中的几何与剂量网格，以及 `reconstruct.py` 的 object/projection metadata。当前程序是一个明确的小型科研算例，不是可自动识别任意设备和任意患者的通用重建器。

图像使用 SimpleITK 的物理坐标：size/spacing/origin/direction 都随 MHD 保存。NumPy 顺序是 `[z,y,x]`，PyTomography 是 `[x,y,z]`，代码在接口处显式转置。Slicer 内部显示采用 RAS；使用正常影像加载器时会处理 LPS/RAS 转换，不能只手动翻转数组。

## 3. GATE 10 怎样形成投影

先运行一个方向：

```bash
bash scripts/python.sh nm/gate_acquire.py \
  --phantom "$OUT/phantom" --out "$OUT/acquisition/view-000" \
  --angle 0 --events 20000 --seed 24680
```

`gate_acquire.py` 使用真实的 GATE/Geant4 输运，发射 208 keV 光子。为了演示投影接口，方向强制为世界坐标 `-y`，探测面位于 y=-100 mm。每个角度旋转水圆柱，并把 VoxelSource 附着在该圆柱上；圆柱本身轴对称，旋转只改变非对称活度分布的朝向。

**不要把 VoxelSource 的旋转只写进 `source.position.rotation`。** 在本次 10.1.1 实测中，该字段没有旋转体素分布。工作代码使用 `water.rotation` + `source.attached_to`，并保持 `direction_relative_to_attached_volume=False`，让束流方向仍为世界坐标的 -y。这个问题是在检查 180° 投影的命中位置时发现并修正的。

PhaseSpaceActor 保存进入探测面的 `PrePosition`、`PreDirection`、`KineticEnergy`、`ParentID`、`EventID`。重建前只保留 207.99 keV 以上、母粒子编号为零且仍沿 -y 的光子，形成理想主光子投影。它不等价于真实扫描仪的能量响应和散射校正。

完整的 24 方向循环由 `scripts/run.sh` 执行。需要整条路线时运行：

```bash
bash scripts/run.sh "$OUT"
```

参数通过 **Bash 环境变量**调整：

```bash
NM_VIEWS=24 NM_VIEW_EVENTS=50000 NM_DOSE_EVENTS=200000 bash scripts/run.sh "$OUT"
```

OSEM 使用 4 个子集，角度数应至少为 4 且是 4 的倍数。为了避免覆盖前一次结果，给新实验使用新的 `OUT`。

## 4. SimpleITK 怎样处理 CT 和标签

```bash
bash scripts/python.sh nm/prepare_images.py \
  --ct "$OUT/phantom/ct_HU.mhd" \
  --reference "$OUT/phantom/activity_truth_Bq_voxel.mhd" \
  --labels "$OUT/phantom/labels.mhd" --out "$OUT/prepared"
```

CT 使用线性插值，分区标签使用最近邻，输出网格来自 reference。默认算例共用一个坐标系，因此使用单位变换。若输入是临床 CT DICOM 文件夹，`--ct` 可以指向该文件夹；存在多个序列时必须用 `--series-id` 指定。程序不上传 DICOM。

若已经在 Slicer 或 SimpleITK 中获得配准变换，可以传入：

```bash
# transform 必须把参考图像的物理点映射到输入 CT/标签的物理点。
bash scripts/python.sh nm/prepare_images.py \
  --ct /local/CT --reference /local/reconstruction-grid.mhd \
  --labels /local/labels.mhd \
  --reference-to-moving-transform /local/reference-to-moving.h5 \
  --out "$OUT/prepared"
```

**重采样不是配准。** 本脚本不会自动估计配准，也不会证明影像已对齐。真实多时间点研究应先估计变换，再在 Slicer 中叠加检查骨性结构、器官边界和分区。非刚性变换还需要明确活度浓度与质量守恒的处理。

不要将 Bq/voxel 图像直接当作任意强度图插值后继续求和。改变体素体积时，应先明确活度浓度单位及积分守恒方式；本脚本只重采样 CT 和标签，活度参考网格保持不变。

## 5. PyTomography 怎样重建和定标

完成所有投影后：

```bash
bash scripts/python.sh nm/reconstruct.py --run "$OUT" --views 24 --iters 8
```

处理顺序是 ROOT 相空间 → 32×8 的探测像素直方图 → `[角度,横向,轴向]` 计数 → SPECTSystemMatrix → PoissonLogLikelihood → 8 次、4 子集 OSEM。

PyTomography 的体素尺寸使用 **cm**，所以 4 mm 写成 0.4 cm。默认水的衰减系数取 0.135 cm⁻¹，作为可见的教学近似；真实 CT→μ 转换必须使用相应能量和扫描仪标定。掩膜外活度设为零，然后用已知定标体模总活度求比例。

```text
factor = known_calibration_activity_Bq / sum(reconstruction)
activity_Bq_per_voxel = reconstruction × factor
```

`reconstruction.json` 保存角度、接受计数、比例因子和简化假设。真实患者没有已知的体内总活度真值，必须通过独立相机灵敏度、扫描时长、分支比、散射、衰减及恢复系数等建立定量关系。不能继续使用本算例的已知 1 MBq 归一化。

`image_metrics.json` 用本地合成真值测量空间质心、热点均值和相对 L2 误差。该值用于发现坐标和重建问题，不设置一个随意的“通过率”。

## 6. 怎样从重建活度计算剂量率

```bash
bash scripts/python.sh nm/gate_dose.py --run "$OUT" --events 100000
```

源图为 `activity_recon_Bq_voxel.mhd`，GATE 按体素活度权重采样 `ion 71 177`。启用放射性衰变和 Livermore 电磁物理，以零母核寿命生成每次 Lu-177 衰变的粒子，统计 100,000 个母核事件。实际轨迹与步数记录在 `gate-dose/statistics.txt`。

DoseActor 的 `dose_sum_Gy.mhd` 是所有母核历史的剂量和：

```text
Gy/decay = dose_sum_Gy / N_parent_decays
Gy/s = Gy/decay × total_activity_Bq
```

本算例的时间序列使用同一个空间分布，剂量率按 `2^(-t/6h)` 缩放。`normalization.json` 记录这个归一化。DoseActor 的相对不确定度属于 MC 计分统计，不代表整个患者剂量结果的不确定度。

当前水圆柱剂量模型与 CT 几何不是自动绑定的。要做患者剂量，需在 GATE 建立 Image volume，使用实验标定的 HU→组织/密度映射，并让活度源、输运几何、分区和 DoseActor 的坐标一致；修改材料和密度后重新检查体素质量及单位。

## 7. 怎样传递给 OpenDose3D

本项目的自动接口是外部 GATE 10 剂量率图 + 明确的时间点。运行：

```bash
export NM_RUN_DIR="$OUT"
xvfb-run -a env QT_QPA_PLATFORM=xcb bash scripts/slicer.sh \
  --no-splash --no-main-window --python-script slicer/integrate_and_view.py
```

脚本在 **Slicer 自带 Python** 中导入 `OpenDose3DLogic` 和 `Logic.fitutils.MonoExponential`，而不是把 OpenDose3D 名字写在自制积分函数上。输入时间单位是秒、剂量率是 Gy/s；拟合后的 AUC 单位因此是 Gy。拟合积分范围为 0 到无穷，采用单指数模型。

默认时间点共用空间分布，因此先拟合共有的动力学因子，再生成体素剂量图；分区平均剂量率也分别调用同一个上游拟合类求 AUC。这个简化不适用于各时间点活度分布显著不同的情形。

输出包括 `dose_integrated_Gy.mhd`、`opendose3d_regions.csv`、`opendose3d.json` 和 `dosimetry.mrb`。JSON 还保存单指数积分的解析值，便于检查秒/小时转换。

本适配器不会替用户创建完整的 OpenDose3D 临床参数节点或 DICOM 给药信息。要使用上游 GUI 的 Initialization、Registration、Segmentation、Time integration 全流程，应按[官方手册](https://gitlab.com/opendose/opendose3d/-/blob/develop/User_Manual.md)准备真实定量 SPECT/PET、CT 和给药信息；不要把已定标 Bq/voxel 再按 counts 或 Bq/ml 重标一次，也不要对采集时刻活度重复做衰变校正。

## 8. 怎样查看和继续处理

```bash
bash scripts/python.sh nm/plot_results.py --run "$OUT"
bash scripts/slicer.sh "$OUT/dosimetry.mrb"
```

Slicer 中的热点应位于真值定义的偏心位置；通过十字线读出 mm 坐标，不能只比较截图方向。前景选择剂量或活度，使用透明度滑块与 CT 叠加；Segmentations 中可以修改分区。

MHD 文件和同名 RAW 必须一起移动。MRB 是包含影像和节点的场景包，可整体保存；先在 Windows 资源管理器进入 `\\wsl.localhost\AlmaLinux-9.6\root\sim-data\nm-dose-workflow`，也可以复制到自己的本地科研数据盘。

## 9. 常见问题

| 现象 | 处理 |
|---|---|
| GATE/ITK 加载了错误的库 | 用 `scripts/python.sh`，不要在 ROOT/Geant4 的全局 LD_LIBRARY_PATH 下直接调用 venv Python |
| 找不到 `slicer` 或 `Logic` | OpenDose3D 脚本必须由 `scripts/slicer.sh` 启动，外部 Python 无法提供 Slicer MRML |
| 找不到 Qt offscreen 插件 | 该 Slicer 包使用 xcb；自动运行用 `xvfb-run`，交互查看用 WSLg |
| 所有角度投影热点都在相同位置 | 检查体素源是否附着到实际旋转的 volume，不要仅改 position.rotation |
| 剂量差 3600 倍 | 检查时间是否从小时转换为秒，以及剂量率是否确实为 Gy/s |
| MHD 加载失败 | 确认 RAW 文件和 MHD 同在、文件名未变 |
| 环境装在别的目录 | Bash 设置 `NM_STACK_HOME`；PowerShell 的发行版/用户名可用对应参数修改 |
| pip check 在 itk wheel 标签处抛出 ValueError | 见验证记录中的具体上游元数据问题；不要通过修改物理模型来处理包标签解析错误 |

教程命令围绕本仓库的真实代码。更换成像设备、材料或临床输入后，需要重新验证物理模型和定量关系。
