# 📈 微博热搜 AI 实时洞察平台 (Weibo Hot Search AI Insight)

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B)
![OpenAI](https://img.shields.io/badge/LLM_API-OpenAI_Compatible-green)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

基于大语言模型（LLM）与自动化 Web 爬虫的**社情民意实时监控与分析看板**。本项目旨在通过技术手段打通“数据采集 - 语义分析 - 交互可视化 - 沉淀存储”的完整业务闭环，探索自动化 AI Agent 在社交媒体趋势分析中的应用潜力。

🌐 **在线体验体验：** [点击这里访问项目主页] *(注：请将此处替换为你的实际 Streamlit 链接)*

---

## ✨ 核心特性 (Key Features)

* 🕷️ **深度自动化采集**：摒弃简单的标题抓取，通过模拟 PC 端用户行为，深入提取每条热搜的首条博文摘要、博主信息及源链接，突破基础反爬限制。
* 🧠 **Universal AI 语义分类引擎**：
    * 内置零样本提示词工程（Zero-Shot Prompting），驱动大模型将复杂网络语境下的热搜精准归入 9 大社会学分类（社会、文娱、科技、财经等）。
    * **高度解耦架构**：支持动态切换任何兼容 OpenAI 格式的 API 接口（如 xAI, DeepSeek, OpenAI 等），用户可自由配置 Base URL 与模型名称。
* 📊 **极简交互式可视化**：彻底摒弃传统静态图表，采用流式渲染的现代化 Web 图表。彻底解决跨平台字体乱码问题，提供平滑的悬停与数据交互体验。
* 💾 **双轨数据持久化**：
    * 本地 SQLite 数据库自动记录历史热度趋势。
    * 支持单次分析结果一键导出为带直达链接的 `.xlsx` 数据快照备份。
* 🎨 **克制的设计美学**：侧边栏采用群青 (Ultramarine) 与天蓝 (Sky Blue) 交织的极简 UI 设计，兼顾操作的直观性与视觉的高级感。

---

## 🛠️ 技术栈 (Tech Stack)

* **前端交互与框架**：Streamlit, HTML/CSS (UI 注入)
* **网络与数据采集**：`httpx`, `BeautifulSoup4` (`lxml` 解析器)
* **大语言模型接入**：`openai` (Python SDK)
* **数据清洗与存储**：`pandas`, `sqlite3`, `openpyxl`

---

## 🚀 本地运行部署 (Local Setup)

### 1. 克隆仓库
```bash
git clone [https://github.com/您的用户名/Weibo-Hot-Search-Web-Crawler.git](https://github.com/您的用户名/Weibo-Hot-Search-Web-Crawler.git)
cd Weibo-Hot-Search-Web-Crawler

2. 安装依赖
建议使用虚拟环境（如 venv 或 conda）进行安装：

Bash
pip install -r requirements.txt
3. 配置核心凭证 (Secrets)
在项目根目录创建 .streamlit 文件夹，并在其中创建 secrets.toml 文件：

Bash
mkdir .streamlit
touch .streamlit/secrets.toml
在 secrets.toml 中填入你的微博 Cookie（用于突破访问限制）：

Ini, TOML
# 必须配置项：浏览器无痕模式下抓取的微博有效 Cookie
WEIBO_COOKIE = "SUB=...; SUBP=...;"

# 可选配置项：如果你想在本地设置默认 API Key
API_KEY = "your_default_api_key"
(⚠️ 警告：请确保持有该凭证的文件 .streamlit/ 已被加入 .gitignore，切勿将其提交至公开仓库！)

4. 启动平台
Bash
streamlit run app.py
☁️ 云端部署建议 (Cloud Deployment)
本项目已针对 Streamlit Community Cloud 进行了深度适配：

移除或忽略了任何本地网络代理配置，确保在海外云服务器环境下的网络直连。

部署时，请在 Streamlit 后台的 Advanced settings -> Secrets 中，将本地 secrets.toml 的内容完整粘贴进去即可实现无缝上线。

云端存储具有易失性，若需重置测试数据，直接在后台 Reboot App 即可生成纯净环境。

⚠️ 免责声明 (Disclaimer)
学习与学术用途：本项目代码仅供 Python 爬虫技术与大语言模型应用的学习、研究和交流使用。

遵守平台规范：请合理设置采集频率。切勿用于高频恶意请求、商业牟利或其他侵犯新浪微博平台权益的行为。因违规使用本代码造成的任何法律纠纷或账号封禁，概不负责。

隐私保护：本项目运行时的数据处理均在内存或用户配置的本地数据库中进行，不收集、不上传任何用户的 API 密钥。
