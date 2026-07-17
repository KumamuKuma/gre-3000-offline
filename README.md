# GRE 3000 词离线版

一个面向 Windows 的离线 GRE 词汇桌面应用。词库随程序只读发布，搜索、学习进度、收藏、随机队列和设置均在本机保存；正常使用不需要联网。

## 使用发布版

双击 `outputs/GRE 3000 词离线版.exe` 即可启动。程序会把个人数据写入：

```text
%APPDATA%\GRE Vocab Offline\GRE 3000 词离线版
```

其中 `user.db` 保存进度、收藏和设置，`logs/app.log` 保存滚动日志。词库和运行组件只会解包到系统临时目录，程序正常退出后自动清理，不会写入或覆盖个人数据。因此以后直接替换 EXE 即可升级，原有进度仍会保留。

首次运行未签名的个人构建时，Windows SmartScreen 可能显示警告。请先确认文件来源和 SHA-256，再选择“更多信息”继续运行。

## 学习方式

- 顺序学习：按原书顺序浏览，并记住当前位置。
- 随机学习：使用持久化随机队列，可按“重新洗牌”生成新顺序。
- 阅读模式：直接显示释义和例句。
- 回忆模式：先隐藏答案，按空格或点击界面控件显示答案；切换模式不会跳到另一个词。
- 生词本：按 `S` 或点击“收藏”保存当前词。
- 朗读：按 `P` 或点击“朗读”。检测到英文语音时可在设置中选择；没有英文语音但系统默认语音可用时会回退到系统默认语音；语音引擎完全不可用时仅禁用朗读，其余功能仍可使用。

快捷键：

| 快捷键 | 功能 |
| --- | --- |
| `Ctrl+F` | 聚焦首页搜索框 |
| `←` / `→` | 上一词 / 下一词 |
| `Space` | 回忆模式显示或隐藏答案 |
| `P` | 朗读当前单词 |
| `S` | 收藏或取消收藏当前单词 |

## 开发与验证

项目使用 Python 3.12、PySide6 6.11.1 和 SQLite。测试在受限 Windows 环境下可这样运行：

```powershell
$env:TEMP = (Join-Path (Get-Location) 'work/test-temp')
$env:TMP = $env:TEMP
$env:QT_QPA_PLATFORM = 'offscreen'
$env:GRE_SOURCE_PDF = 'D:\桌面\LGU\GRE\张巍GRE镇考3000词-乱序（2026年）.pdf'
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
.\.venv\Scripts\python.exe -m pytest -v -p no:cacheprovider
```

发布构建另外需要在项目 `.venv` 中安装 Pillow 和 Nuitka 4.1.3（以及 Nuitka 的 `ordered-set`、`zstandard` 依赖），并需要本机 C 编译器。发布脚本先用 `pyside6-deploy` 生成 ASCII 名的 Qt onefile runtime，再用 stdlib-only Nuitka onefile 外壳生成最终中文文件名；外壳不导入 Qt，也不会把 runtime 复制到持久目录：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_release.ps1
```

脚本会依次执行全量测试、严格词库导入、数据库/审计核对、SVG→ICO 生成、内外层 onefile 构建和完整进程链原生窗口 smoke。只有这些检查全部通过后，EXE、使用说明和审计报告才会作为同一个发布集替换；任一替换失败会恢复整套旧文件。脚本还会输出最终单文件 EXE 的 SHA-256 与字节数。严格导入预期为 3,292 条记录、0 条未解决问题、5 条已人工复核记录，SQLite 完整性检查为 `ok`。

发布目录包含：

- `outputs/GRE 3000 词离线版.exe`
- `outputs/使用说明.txt`
- `outputs/词库导入审计报告.html`

SVG 图标为本项目原创的打开书本与 GRE 字母组合，不包含第三方 logo、二维码或广告素材。
