# 每日热量消耗计算器

## 立即使用

**[在线使用](https://liu602112-cpu.github.io/daily-energy-calculator/)** · **[下载离线版 ZIP](https://liu602112-cpu.github.io/daily-energy-calculator/downloads/daily-energy-calculator.zip)**

在线版支持手机和电脑浏览器。离线版下载后解压，双击 `index.html` 即可使用，无需安装。在线页面右上角也提供下载入口。

根据开发文档实现的纯前端三步计算器，无需安装依赖、账号、数据库或外部接口。输入只保留在当前页面内存中，刷新或关闭页面即清除。

![完整功能展示：身体信息、生活方式与消耗结果](feature-overview.png)

[查看完整结果页](mobile-result.png)

## 使用

直接双击 `dist/index.html` 即可离线使用。将整个 `dist` 文件夹复制到其他设备也能使用；所有文件必须保持在同一目录。手机端也可通过静态网站服务打开。

本机预览：运行 `node server.cjs` 后打开 http://127.0.0.1:4173。

## 文件

- `dist/index.html`：三步页面和语义表单。
- `dist/styles.css`：深色界面与移动端适配。
- `dist/calculator.js`：独立计算与校验逻辑，兼容浏览器和 Node.js。
- `dist/app.js`：步骤切换、结果展示和修改重算。
- `tests/calculator.test.cjs`：公式、活动系数与边界验证。

在线版本通过 GitHub Pages 发布，发布目录为 `dist`，对应 `gh-pages` 分支。

运行计算测试：`node --test tests/calculator.test.cjs`。

未填写体脂率使用 Mifflin-St Jeor；填写后使用 Katch-McArdle。活动系数严格采用文档中的 4×4 表。内部计算不提前舍入，仅展示时四舍五入至整数 kcal。

本工具仅供普通成年用户估算，保留文档要求的适用人群与个体差异提示。未加入饮食建议、历史记录或后端服务。
