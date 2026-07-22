# GRE 3000 词离线版

一个面向 Windows 的离线 GRE 词汇桌面应用。词库随程序只读发布，搜索、List 学习进度、星级和设置均在本机保存；正常使用不需要联网。

## 使用发布版

双击 `outputs/GRE 3000 词离线版.exe` 即可启动。程序会把个人数据写入：

```text
%APPDATA%\GRE Vocab Offline\GRE 3000 词离线版
```

其中 `user.db` 保存各 List 的位置与完成次数、星级和设置，`logs/app.log` 保存滚动日志。词库和运行组件只会解包到系统临时目录，程序正常退出后自动清理，不会写入或覆盖个人数据。因此以后直接替换 EXE 即可升级，原有进度仍会保留。旧版 4、5 星会在升级时合并为 3 星；旧收藏和逐词已背次数不再显示。

首次运行未签名的个人构建时，Windows SmartScreen 可能显示警告。请先确认文件来源和 SHA-256，再选择“更多信息”继续运行。

## 学习方式

- 选择 List 学习：可主动选择 List 1–30 或两个补充 List；每个 List 独立记住当前位置。
- List 已背次数：完整走到所选 List 最后一个词后，点击“完成本轮”会增加一次；首页也可用 `− / +` 手动修正所选 List 的次数。
- 按星级学习：在所选 List 内选择全部、0、1、2 或 3 星；筛选后仍按原书顺序。
- 阅读模式：直接显示完整释义、近义词和例句。
- 简义模式：直接显示精简的英中释义，不需要点击揭晓。
- 回忆模式：先隐藏答案，按空格或点击界面控件后显示精简英中释义；切换模式不会跳到另一个词。
- 四选一模式：从四个词义中选择答案，提交后标出正确项，不会自动跳到下一词。
- 星级标注：学习页右上角显示 0 至 3 星；每次点击增加一星，3 星后再次点击回到 0 星。
- 词根与近形词：词库中可可靠匹配的同词根/同族词，以及拼写相近但词义不同的词，会列在单词下方并可点击打开。回忆模式揭晓前、四选一作答前会隐藏这些提示，避免泄题。
- 真经等价词：只收录《真经 GRE 等价词汇总》直接列明、且能与主词库精确匹配的关系；在任一端打开词条都能看到另一端，不做未经原书支持的传递扩展。
- 机经 7.0 重点：同时收录于《GRE 镇考机经词 7.0》的词会在学习页和完整词表中以橙色“重点”标识。
- 完整词表：按原书顺序查看全部单词与所属 List，可筛选、查看机经 7.0 标记并修改 0 至 3 星。
- 朗读：按 `P` 或点击“朗读”。设置中可开启“切换到下一词时自动朗读一次”。检测到英文语音时可选择语音；没有英文语音但系统默认语音可用时会回退；语音引擎完全不可用时仅禁用朗读，其余功能仍可使用。

快捷键：

| 快捷键 | 功能 |
| --- | --- |
| `Ctrl+F` | 聚焦首页搜索框 |
| `←` / `→` | 上一词 / 下一词 |
| `Space` | 回忆模式显示或隐藏答案 |
| `P` | 朗读当前单词 |

## 开发与验证

项目使用 Python 3.12、PySide6 6.11.1 和 SQLite。测试在受限 Windows 环境下可这样运行：

```powershell
$env:TEMP = (Join-Path (Get-Location) 'work/test-temp')
$env:TMP = $env:TEMP
$env:QT_QPA_PLATFORM = 'offscreen'
$env:GRE_SOURCE_PDF = 'D:\桌面\LGU\GRE\张巍GRE镇考3000词-乱序（2026年）.pdf'
$env:GRE_EQUIVALENCE_PDF = 'D:\桌面\LGU\GRE\真经GRE等价词汇总.pdf'
$env:GRE_MACHINE7_PDF = 'D:\桌面\LGU\GRE\GRE镇考机经词7.0-乱序（2026年版）.pdf'
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
.\.venv\Scripts\python.exe -m pytest -v -p no:cacheprovider
```

发布构建另外需要在项目 `.venv` 中安装 Pillow 和 Nuitka 4.1.3（以及 Nuitka 的 `ordered-set`、`zstandard` 依赖），并需要本机 C 编译器。发布脚本先用 `pyside6-deploy` 生成 ASCII 名的 Qt onefile runtime，再用 stdlib-only Nuitka onefile 外壳生成最终中文文件名；外壳不导入 Qt，也不会把 runtime 复制到持久目录：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_release.ps1
```

脚本会依次执行全量测试、严格词库导入、数据库/审计核对、SVG→ICO 生成、内外层 onefile 构建和完整进程链原生窗口 smoke。只有这些检查全部通过后，EXE、使用说明和审计报告才会作为同一个发布集替换；任一替换失败会恢复整套旧文件。脚本还会输出最终单文件 EXE 的 SHA-256 与字节数。严格导入预期为 3,292 条记录、0 条未解决问题、203 条已人工复核记录、547 条原书直接等价词边、1,410 个机经 7.0 重点词，SQLite 完整性检查为 `ok`。

发布目录包含：

- `outputs/GRE 3000 词离线版.exe`
- `outputs/使用说明.txt`
- `outputs/词库导入审计报告.html`

SVG 图标为本项目原创的打开书本与 GRE 字母组合，不包含第三方 logo、二维码或广告素材。
