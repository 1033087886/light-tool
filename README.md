# 车灯动画编辑器

Windows 桌面 EXE 工具，用于编辑一维车灯 LED 灰度动画并导出 C 数组。

## 功能

- 设置 LED 数量和帧数量，编辑每帧 0-255 灰度值。
- 每帧独立 `duration_ms`，可在时间轴双击帧间隔数字直接修改。
- 帧新增、插入、复制、删除。
- 画笔拖拽编辑、选区填充、清空、复制上一帧。
- 流水、流星、双侧向中心聚集，以及全段呼吸、中心点亮、中心外扩、两侧填充、分段闪烁、中心扩张追光、分层堆叠追光等常用尾灯效果生成器。
- JSON 工程保存/加载。
- 导出 C 头文件，包含 LED 数、帧数、帧时长数组和二维灰度数组。

## 开发运行

```powershell
python main.py
```

## 测试

```powershell
python -m unittest discover -s tests -v
```

## 打包

```powershell
pyinstaller --noconfirm --clean --windowed --onedir --name LightAnimator main.py
```

打包完成后运行：

```powershell
dist\LightAnimator\LightAnimator.exe
```
