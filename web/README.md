# GRE 3000 PWA

适配 iPhone、iPad 和桌面浏览器的 GRE 3000 可安装网页应用。

- 四种学习模式与 0～3 星标注；
- 原书 List 顺序、等价词、词根词和近形异义词；
- Service Worker 离线缓存；
- JSON 进度文件与 Windows 桌面版双向导入/导出；
- ChatGPT 登录后的 D1 自动云同步；
- 一次性 Windows 设备令牌。

```powershell
npm install
npm run dev
npm test
```

词库数据由仓库根目录的 `scripts/export_web_data.py` 从已审核 SQLite 数据库生成。
