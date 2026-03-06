# 涛割 - AI视频生成平台

基于PyQt6的中高端精品短剧AI视频生成平台，聚焦"先图后视频(I2V)+多模型智能路由+标准化精品流程"模式。

## 功能特点

- **先图后视频流程**: 先生成静态图像确认效果，再转换为动态视频
- **多模型智能路由**: 支持Vidu/Kling/Jimeng/ComfyUI等多模型，根据场景自动选择最优模型
- **角色一致性**: 支持角色库管理和一致性控制
- **首尾帧控制**: 支持视频首尾帧精确控制
- **积分制计费**: 实时成本追踪和预算控制
- **剪映导出**: 支持导出剪映项目文件
- **双模式UI**: 向导模式(Wizard)和画布模式(Canvas)

## 目录结构

```
taoge/
├── src/
│   ├── main.py                    # 程序入口
│   ├── config/                    # 配置模块
│   │   ├── settings.py            # 配置管理
│   │   └── constants.py           # 常量定义
│   ├── database/                  # 数据库模块
│   │   ├── models/                # ORM模型
│   │   └── session.py             # 会话管理
│   ├── services/                  # 服务层
│   │   ├── generation/            # 生成服务
│   │   │   ├── base_provider.py   # Provider基类
│   │   │   ├── model_router.py    # 模型路由器
│   │   │   └── closed_source/     # 闭源API实现
│   │   ├── scene/                 # 场景处理
│   │   │   ├── processor.py       # SRT解析
│   │   │   └── prompt_generator.py# Prompt生成
│   │   ├── task_queue/            # 任务队列
│   │   └── export/                # 导出服务
│   ├── ui/                        # UI层
│   │   ├── main_window.py         # 主窗口
│   │   └── resources/             # 资源文件
│   └── utils/                     # 工具模块
├── tests/                         # 测试
├── data/                          # 数据存储
├── generated/                     # 生成输出
├── materials/                     # 素材库
└── requirements.txt               # 依赖
```

## 安装

```bash
cd taoge
pip install -r requirements.txt
```

## 运行

```bash
python src/main.py
```

## 核心架构

### 五层架构

1. **UI层**: PyQt6桌面应用，双模式切换
2. **控制器层**: 项目控制、生成控制
3. **服务层**: 场景处理、图像/视频生成、任务队列、成本追踪
4. **数据层**: SQLite + SQLAlchemy ORM
5. **外部集成层**: 闭源API + 开源ComfyUI

### 设计模式

- **Strategy**: 多模型Provider统一接口
- **Factory + Router**: 智能模型路由
- **Observer**: 任务进度实时推送
- **Singleton**: 配置、日志管理

## 开发计划

| 阶段 | 内容 | 状态 |
|------|------|------|
| 第1-2周 | 基础框架、配置、数据库 | ✅ 完成 |
| 第3-4周 | 场景处理、Prompt生成 | ✅ 完成 |
| 第5-6周 | 视频生成、任务队列 | ✅ 完成 |
| 第7-8周 | UI双模式、预览组件 | 🔄 进行中 |
| 第9周 | 高级控制、ComfyUI集成 | ⏳ 待开始 |
| 第10周 | 素材库、成本追踪 | ⏳ 待开始 |
| 第11-12周 | 测试、优化、文档 | ⏳ 待开始 |

## API配置

在首次运行时，需要在设置中配置以下API密钥：

- **DeepSeek**: 用于AI标签生成和动作分析
- **Vidu/Kling/Jimeng**: 图像和视频生成（按需配置）

## 许可证

私有软件，保留所有权利。
