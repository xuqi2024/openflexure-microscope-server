# OpenFlexure Microscope Software

> ## This is the v3 development branch
> We are no longer actively developing v2, but v3 is not yet released.
> v3 is not yet stable enough for wider public release. Development snapshots are released from time to time.
> If you want to use a development snapshot before we do a wider alpha release the best thing to do is get in contact on the [forum](https://openflexure.discourse.group/).
 If you want to look at the code for v2 you should look at the [master branch](https://gitlab.com/openflexure/openflexure-microscope-server/-/tree/master).

## 📚 文档目录

- [项目架构与功能概述](#项目架构与功能概述) - 了解系统架构和核心功能
- [快速上手指南](#快速上手指南) - 快速开始使用
- [项目结构详解](#项目结构详解) - 代码结构和技术细节
- [Getting started](#getting-started) - 基础安装指南
- [Running directly](#running-directly) - 直接运行服务器
- [Settings](#settings) - 配置说明
- [Developer guidelines](#developer-guidelines) - 开发指南

---

The "server" is the main component of the OpenFlexure Microscope's software.  It is responsible for controlling microscope hardware, data management, and allowing it to be controlled locally and over a network.
This repository includes the graphical interface, which is implemented as a web application served from the root of the Python web server. The simplest way to use it is via OpenFlexure eV, which should find your microscope on the network, and display the interface. The microscope's interface can also be accessed at `http://microscope.local:5000/` in a web browser, assuming the hostname of your microscope is `microscope`.

This software runs on [LabThings-FastAPI](https://github.com/labthings/labthings-fastapi/), which creates an HTTP server using FastAPI (which in turn relies on Starlette and pydantic).

## 项目架构与功能概述

### 整体架构

OpenFlexure显微镜服务器是一个基于**LabThings-FastAPI**框架构建的分布式显微镜控制系统，采用模块化的"Thing"架构设计：

```
显微镜服务器架构
├── HTTP/WebSocket API 服务器 (FastAPI)
│   ├── 静态文件服务 (Vue.js 前端)
│   ├── RESTful API 端点
│   └── MJPEG 视频流
├── Thing 管理系统 (组件化硬件抽象)
│   ├── 相机控制 (/camera/)
│   ├── 载物台控制 (/stage/)
│   ├── 自动对焦 (/autofocus/)
│   ├── 智能扫描 (/smart_scan/)
│   ├── 相机-载物台映射 (/camera_stage_mapping/)
│   ├── 自动居中 (/auto_recentre_stage/)
│   ├── 系统控制 (/system_control/)
│   └── 设置管理 (/settings/)
└── 配置与数据管理
    ├── JSON 配置文件 (ofm_config.json)
    ├── 持久化设置存储
    └── 日志管理
```

### 核心功能模块

#### 1. 硬件控制层
- **相机控制** (`/camera/`): 支持PiCamera2、OpenCV、模拟相机
  - 实时视频流 (MJPEG)
  - 图像捕获 (JPEG/PNG/RAW)
  - 相机参数调节 (曝光、增益、白平衡等)
  - 多分辨率支持

- **载物台控制** (`/stage/`): 支持Sangaboard、虚拟载物台
  - 三轴精密定位 (X/Y/Z)
  - 相对/绝对移动
  - 位置记忆与回归
  - 回程间隙补偿

#### 2. 智能功能层
- **自动对焦** (`/autofocus/`): 基于图像锐度的智能对焦
  - JPEG锐度监测算法
  - 多步骤自动对焦流程
  - 对焦质量评估与报告
  - 焦点位置优化

- **智能扫描** (`/smart_scan/`): 大视野图像拼接扫描
  - 网格化自动扫描
  - 智能焦点跟踪
  - 背景检测与样品识别
  - 图像拼接与导出

- **相机-载物台映射** (`/camera_stage_mapping/`): 空间校准系统
  - 像素到物理坐标的映射
  - 闭环位置控制
  - 一维/二维校准算法
  - 回程间隙测量与补偿

#### 3. 系统服务层
- **设置管理** (`/settings/`): 集中化配置管理
  - 外部元数据存储
  - 显微镜唯一标识
  - 嵌套字典配置
  - 热更新支持

- **系统控制** (`/system_control/`): 系统级操作
  - 系统状态监控
  - 服务管理
  - 硬件重启控制

### 前端架构

#### Vue.js Web应用 (`webapp/`)
- **技术栈**: Vue.js 2.x + Vuex + UIKit
- **功能模块**:
  - 实时相机预览
  - 载物台控制界面
  - 扫描任务管理
  - 设置配置界面
  - 图像浏览与管理
  - ImJoy插件支持

#### 界面组件
- `appContent.vue`: 主界面容器
- `tabContentComponents/`: 功能标签页
  - `captureContent.vue`: 图像捕获
  - `navigateContent.vue`: 载物台导航
  - `backgroundDetectContent.vue`: 背景检测
  - `extensionContent.vue`: 扩展功能
- `labThingsComponents/`: 通用控制组件
- `modalComponents/`: 弹窗组件

### 配置系统

#### 多环境配置支持
- `ofm_config_full.json`: 完整硬件配置 (PiCamera2 + Sangaboard)
- `ofm_config_simulation.json`: 仿真模式配置
- `ofm_config_stub.json`: 开发测试配置 (OpenCV Camera + Dummy Stage)

#### 运行时配置
- **Things配置**: 动态加载硬件抽象层
- **设置持久化**: `/var/openflexure/settings/` 存储用户配置
- **日志管理**: 轮转日志文件，最大1MB，保留10个备份

### 部署与兼容性

#### 生产环境 (Raspberry Pi)
- **系统服务**: `systemd` 管理的后台服务
- **端口**: 默认5000端口
- **主机名**: `microscope.local`
- **用户**: `openflexure-ws` 专用用户

#### 开发环境
- **Python**: 3.9+ 支持
- **依赖管理**: `pyproject.toml` + `pip`
- **前端构建**: Node.js + npm
- **测试**: pytest + FastAPI TestClient

### API接口

#### RESTful API
- **OpenAPI 3.0**: 自动生成的API文档
- **Thing-based**: 每个硬件组件独立的API端点
- **异步操作**: 支持长时间运行任务的进度追踪
- **兼容性**: v2 API兼容层 (用于OpenFlexure Connect)

#### 数据格式
- **图像**: JPEG/PNG/RAW数组
- **位置**: 三维坐标数组
- **配置**: JSON嵌套对象
- **流媒体**: MJPEG over HTTP

## Getting started

A general user-guide on setting up your microscope can be found [**here on our website**](https://www.openflexure.org/projects/microscope/).
This includes basic installation instructions suitable for most users.
The simplest way to set up a microscope is to download the pre-built Raspberry Pi SD card image, which has this server already installed, along with all of its dependencies.
There are instructions on how to [use the microscope](https://openflexure.org/projects/microscope/control) once you have installed the software, either from OpenFlexure Connect, or through a web browser.
The web server starts on port 5000 by default, and the microscope SD image uses the hostname "microscope" so you can usually access the web interface at <http://microscope.local:5000/>.

A user guide and developer documentation **for v2 of the server** can be found on [**ReadTheDocs**](https://openflexure-microscope-software.readthedocs.io/), including some installation notes, a link to the HTTP API reference, and guidance for developing extensions.
More information is also available in the [handbook](https://gitlab.com/openflexure/microscope-handbook/), and in the "development instructions" below.

## 快速上手指南

### 1. 环境选择

根据你的使用场景选择合适的配置：

#### 生产环境（推荐）
```bash
# 使用预构建的树莓派镜像
# 访问 http://microscope.local:5000/
```

#### 开发环境
```bash
# 克隆仓库
git clone https://gitlab.com/openflexure/openflexure-microscope-server.git
cd openflexure-microscope-server

# 设置Python环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv/Scripts/activate  # Windows

# 安装依赖
pip install -e .[dev]

# 启动开发服务器（模拟模式）
openflexure-microscope-server -c ofm_config_stub.json --host 0.0.0.0 --port 5000
```

### 2. 配置文件说明

选择合适的配置文件：

- **`ofm_config_full.json`**: 完整的硬件配置，适用于真实的OpenFlexure显微镜
  - PiCamera2 相机
  - Sangaboard 载物台控制器
  - 所有智能功能启用

- **`ofm_config_simulation.json`**: 仿真模式，用于测试和演示
  - 模拟相机（生成测试图像）
  - 虚拟载物台
  - 所有功能可用但不操作真实硬件

- **`ofm_config_stub.json`**: 开发模式，适用于没有硬件的开发环境
  - OpenCV相机（使用电脑摄像头）
  - 虚拟载物台
  - 适合软件开发和测试

### 3. 基本操作流程

#### 启动服务器
```bash
# 在树莓派上
sudo systemctl start openflexure-microscope-server

# 或手动启动
openflexure-microscope-server -c /path/to/config.json --host 0.0.0.0 --port 5000
```

#### 访问Web界面
1. 打开浏览器访问 `http://microscope.local:5000/` 或 `http://localhost:5000/`
2. 主要界面标签：
   - **Capture**: 图像捕获和预览
   - **Navigate**: 载物台控制和导航
   - **Extensions**: 扩展功能（扫描、自动对焦等）
   - **Settings**: 系统设置和配置

#### 使用API
```python
# Python 客户端示例
import requests

# 获取当前位置
response = requests.get("http://microscope.local:5000/stage/position")
position = response.json()

# 移动载物台
requests.post("http://microscope.local:5000/stage/move_rel", 
              json={"displacement": [10, 0, 0]})

# 拍摄照片
image_response = requests.get("http://microscope.local:5000/camera/capture")
```

### 4. 常用功能

#### 自动对焦
```bash
# 通过API调用
curl -X POST http://microscope.local:5000/autofocus/autofocus
```

#### 智能扫描
```bash
# 启动扫描任务
curl -X POST http://microscope.local:5000/smart_scan/scan \
  -H "Content-Type: application/json" \
  -d '{"scan_params": {"x_size": 5, "y_size": 5}}'
```

#### 获取实时视频流
访问 `http://microscope.local:5000/camera/lores_mjpeg_stream` 获取低分辨率视频流

### 5. 故障排查

#### 常见问题
1. **服务无法启动**
   - 检查配置文件路径和格式
   - 使用 `--fallback` 参数启动错误页面
   - 查看日志：`journalctl -u openflexure-microscope-server`

2. **硬件无法连接**
   - 确认硬件连接正确
   - 检查权限设置
   - 尝试使用仿真配置测试

3. **Web界面无法访问**
   - 确认防火墙设置
   - 检查端口占用：`netstat -tlnp | grep 5000`
   - 尝试使用IP地址而非域名访问

#### 调试模式
```bash
# 停止系统服务
sudo systemctl stop openflexure-microscope-server

# 手动启动以查看详细日志
openflexure-microscope-server -c config.json --host 0.0.0.0 --port 5000 --fallback
```

## 项目结构详解

### 目录结构
```
openflexure-microscope-server/
├── pyproject.toml                 # Python项目配置和依赖
├── README.md                      # 项目文档
├── CHANGELOG.md                   # 版本更新日志
├── LICENSE                        # GPL v3 许可证
├── 
├── 配置文件/
│   ├── ofm_config_full.json       # 完整硬件配置
│   ├── ofm_config_simulation.json # 仿真模式配置
│   └── ofm_config_stub.json       # 开发测试配置
├── 
├── src/openflexure_microscope_server/  # 主要Python代码
│   ├── __init__.py
│   ├── logging.py                 # 日志配置
│   ├── server/                    # 服务器核心
│   │   ├── __init__.py           # 服务器启动逻辑
│   │   ├── legacy_api.py         # v2 API兼容层
│   │   └── serve_static_files.py # 静态文件服务
│   └── things/                   # 硬件抽象层（Thing组件）
│       ├── auto_recentre_stage.py    # 自动居中功能
│       ├── autofocus.py              # 自动对焦系统
│       ├── camera_stage_mapping.py   # 相机-载物台映射
│       ├── settings_manager.py       # 设置管理
│       ├── smart_scan.py             # 智能扫描
│       ├── stitching.py              # 图像拼接
│       ├── system_control.py         # 系统控制
│       ├── test.py                   # API测试组件
│       ├── camera/                   # 相机控制模块
│       │   ├── __init__.py          # 相机基类和协议
│       │   ├── opencv.py            # OpenCV相机实现
│       │   └── simulation.py        # 模拟相机实现
│       └── stage/                    # 载物台控制模块
│           ├── __init__.py          # 载物台基类和协议
│           └── dummy.py             # 虚拟载物台实现
├── 
├── webapp/                        # Vue.js前端应用
│   ├── package.json              # Node.js依赖配置
│   ├── vue.config.js             # Vue构建配置
│   ├── babel.config.js           # Babel转译配置
│   ├── public/                   # 静态资源
│   │   ├── index.html           # 主HTML模板
│   │   ├── favicon.ico          # 图标
│   │   └── *.imjoy.html         # ImJoy插件模板
│   └── src/                      # Vue.js源代码
│       ├── App.vue              # 根组件
│       ├── main.js              # 应用入口
│       ├── store.js             # Vuex状态管理
│       ├── components/           # UI组件
│       │   ├── appContent.vue           # 主界面
│       │   ├── loadingContent.vue       # 加载界面
│       │   ├── fieldComponents/         # 表单组件
│       │   ├── genericComponents/       # 通用组件
│       │   ├── labThingsComponents/     # LabThings组件
│       │   ├── modalComponents/         # 弹窗组件
│       │   └── tabContentComponents/    # 标签页内容
│       │       ├── captureContent.vue   # 图像捕获界面
│       │       ├── navigateContent.vue  # 导航控制界面
│       │       ├── extensionContent.vue # 扩展功能界面
│       │       └── ...
│       └── assets/               # 资源文件
│           └── less/            # 样式文件
├── 
├── tests/                        # 测试代码
│   ├── test_camera.py           # 相机测试
│   └── test_dummy_server.py     # 服务器集成测试
├── 
├── docs/                         # 文档
│   ├── Makefile                 # 文档构建
│   └── requirements.txt         # 文档依赖
└── 
└── scripts/                      # 辅助脚本
    └── zenodo/                  # Zenodo发布脚本
```

### 核心模块说明

#### 1. 服务器核心 (`src/openflexure_microscope_server/server/`)
- **`__init__.py`**: 服务器启动和配置逻辑
  - `serve_from_cli()`: 命令行启动入口
  - `customise_server()`: 服务器自定义配置
- **`legacy_api.py`**: v2 API兼容层，确保与OpenFlexure Connect兼容
- **`serve_static_files.py`**: 静态文件服务，提供Vue.js前端

#### 2. Thing组件系统 (`src/openflexure_microscope_server/things/`)
每个Thing都是一个独立的功能模块，提供特定的硬件控制或软件功能：

- **基础硬件控制**:
  - `camera/`: 相机抽象层，支持多种相机类型
  - `stage/`: 载物台抽象层，支持多种控制器

- **智能功能**:
  - `autofocus.py`: 基于图像锐度的自动对焦算法
  - `smart_scan.py`: 大视野扫描和图像拼接
  - `camera_stage_mapping.py`: 空间校准和坐标映射

- **系统服务**:
  - `settings_manager.py`: 配置管理和持久化
  - `system_control.py`: 系统级操作和控制

#### 3. 前端应用 (`webapp/`)
- **Vue.js 2.x**: 响应式用户界面
- **Vuex**: 状态管理，同步服务器状态
- **UIKit**: UI组件库
- **ImJoy**: 插件系统支持

#### 4. 配置系统
- **多环境配置**: 支持开发、测试、生产环境
- **动态加载**: Thing组件可以通过配置文件动态加载
- **持久化设置**: 用户配置自动保存到文件系统

### 技术特点

#### 1. 模块化架构
- **Thing-based**: 每个硬件组件都是独立的Thing
- **插件式**: 新功能可以作为新Thing轻松添加
- **依赖注入**: LabThings-FastAPI提供的依赖注入系统

#### 2. 异步处理
- **FastAPI**: 基于asyncio的高性能Web框架
- **后台任务**: 长时间运行的操作（如扫描）在后台执行
- **实时更新**: WebSocket支持实时状态更新

#### 3. 硬件抽象
- **协议定义**: 通过Python Protocol定义硬件接口
- **多实现支持**: 同一接口支持多种硬件实现
- **模拟模式**: 无硬件环境下的完整功能模拟

## Running directly

The Python package provides a command `ofm-microscope-server` that runs the server. This is what is used by `systemd` to run the service. You will need to provide some command-line arguments, see the output of `--help` for an up to date list. See `/etc/systemd/system/openflexure-microscope-server.service` for the command line used to run the server by default on the  Raspberry Pi. In general, you are likely to want to specify a configuration file with `-c`, a host (`--host 0.0.0.0` to serve on all addresses) and a port (`--port 5000`). The `--fallback` option will allow the server to start *even if the hardware specified in the configuration file can't load*. This serves an error page, rather than have the server fail. In the future, it should redirect users to a way to fix their configuration.

## Settings

The microscope is initially configured by a LabThings config file. This specifies two important things:

* The Python classes (and initialisation arguments) to use for each `Thing`. This sets the type of camera and stage, and enables/disables additional functionality like scanning and autofocus.
* The location of the settings folder, where each Thing can store its settings.

By default, this configuration file should be read from `/var/openflexure/settings/ofm_config.json` when the microscope is run as a service. If it is run at the command line you should specify the configuration using the `-c` command line flag. This configuration file does not change often, and usually only needs to be updated when you change the physical hardware. It may be that this file should be made read-only, particularly in microscopes deployed for e.g. medical applications.

The settings folder is, by default, `/var/openflexure/settings/` on the SD card, or `./settings/` if run elsewhere. It can be changed in the configuration file. This holds every other persistent setting. Camera settings, calibration data, default capture settings, stream resolution and so on. There is one folder per `Thing`, each with their own file. The settings files can change very regularly, and if you need to reset your settings, it's usually these files that你应该删除或重置。如果您删除一个设置文件，这应该重置相应的“Thing”，您不必删除整个文件夹。

# Developer guidelines

## Developing on a Raspberry Pi

The easiest way to work on the software is to build an OpenFlexure Microscope around a Raspberry Pi, using our custom disk image.  This includes a pre-installed copy of this server, and a pre-built copy of the web application, so it's ready to use.  You can also develop directly on the Raspberry Pi, and this is the best way to test out changes to the Python code using actual hardware.  

You can manage the server with the `ofm` command, using `ofm start`, `ofm stop`, and `ofm restart` to do the respective actions. Often, stopping the server and running it manually will make errors easier to spot. To do this, run:
```
ofm stop
ofm activate
cd /var/openflexure
sudo -u openflexure-ws openflexure-microscope-server --fallback -c microscope_configuration.json --host 0.0.0.0 --port 5000
```

Our favourite way of working with the server on a Pi is to follow the instructions above, then open a VSCode Remote session from another computer.  This allows you to use your usual developer environment to write code, but everything runs on the Raspberry Pi with real hardware.  Note that the repository is cloned by default over `https`, so you will probably need to change the "remote" URL to your fork of the repository, or to SSH, before you're able to push changes.

### Updating just the web app

Installing and running node.js on a Raspberry Pi is slow and often frustrating.  Our preference is to do node.js development on another computer, and connect either to a dummy server on that computer, or to a real microscope elsewhere on the network.  If you only want to work on the Python code, it's possible to download a pre-built web application and use it with your modified Python code.  To do this, locate the archive of the web application, and then run:
```
cd /var/openflexure/
sudo chown -R openflexure-ws.openflexure-ws .
sudo chmod -R g+w .
cd application/openflexure-microscope-server/
sudo rm -rf openflexure_microscope/api/static/dist/
curl <tarball URL> | tar -xz
```
NB the `sudo chown` and `sudo chmod` lines are probably unnecessary, but depending on the state of your system they may fix annoying permissions issues.

To find the `<tarball URL>` you should look for `openflexure-microscope-webapp-<version>.tar.gz` on the [build server](https://build.openflexure.org/openflexure-microscope-server/), or open the `package` job of a CI pipeline on this repository, and locate it by browsing the artifacts.  That should work for any merge request that's currently open.

## Installation on other platforms

The Raspberry Pi image we use currently ships with Python 3.7.3. For local development on a different platform, please use PyEnv or similar to make sure you're running on this version. For example, Windows users can use [Scoop](https://scoop.sh/) to install specific Python versions.  This repository contains two closely related parts; a web server written in Python, that handles hardware control, and a web application using Vue.js that provides a graphical control interface.  It is possible to work on either of these in isolation, but bear in mind that if you only set up Python development, you will need to host the web application elsewhere.

Most of our core team don't run the Javascript development on the Raspberry Pi, as npm can be quite slow to build the application.  Instead, we set up the Python part of the project on a Raspberry Pi, and run the Javascript part on your development machine.  You can then connect to the web application served from your local machine, and enter the address of the Raspberry Pi when the interface first loads.

To set up a development version of the software (most likely using emulated camera and stage if you're not running on a Raspberry Pi):

### Clone the repository
* `git clone https://gitlab.com/openflexure/openflexure-microscope-server.git`
* `cd openflexure-microscope-server`

### Set up the Python environment and run a test server
* (Optional) Set local Python version to 3.11
* Create a virtual environment and activate it:
  * `python -m venv .venv`
  * `source .venv/bin/activate` (on Linux) or `.venv/Scripts/activate` (on Windows)
  * `pip install -e .[dev]` (This will install development dependencies.  If you don't need these, there is probably a simpler way to run the server than cloning this repo.)
* Finally, run the server: currently you can do this with `sudo systemctl start openflexure-microscope-server` if it's pre-installed on a Raspberry Pi, or `openflexure-microscope-server -c ofm_config_stub.json` to run locally.

### Run the server manually on a Raspberry Pi
```
cd /var/openflexure
sudo -u openflexure-ws PATH="/var/openflexure/application/openflexure-microscope-server/.venv/bin/:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin" /var/openflexure/application/openflexure-microscope-server/.venv/bin/openflexure-microscope-serve -c /var/openflexure/settings/ofm_config.json --host 0.0.0.0 --port 5000
```


### Set up the Javascript environment and build

The Labthings-FastAPI server, written in Python, serves a web application written in `Vue.js` (Vue2).  This is distributed with the SD card image for the microscope.

For more details on the web app see the ReadMe in the [webapp](./webapp) directory.


## Python: Formatting, linting, and tests

All of the commands below assume that you are running in the OFM virtual environment, i.e. you have run `ofm activate` on an OpenFlexure SD card, or `source .venv/bin/activate` on Linux, or `.venv/Scripts/activate`on Windows.

**Before committing** you should lint and auto-format your code:

* To lint run `ruff check`
* To auto-format the Python code run `ruff format`
* To auto-format the Javascript code, run
  * `cd webapp`
  * `npm run lint`

**Before merging** please auto-format your code and also run the quality checks (linting, static analysis, and unit tests)

* All commands above
* `mypy src` (currently fails)
* `pytest`

For more details on out Python conventions please see the **[project contributions guide](./CONTRIBUTING.md)**.

### Details

We use several code analysis and formatting libraries in this project. Our CI will check each of these automatically, so ensuring they pass locally will save you time. Currently `ruff` is used for linting/formatting and `pytest` for unit tests. `mypy` will be enabled once the codebase is ready.

## Python environment, build, and dependencies

As of `v3` we specify dependencies in `pyproject.toml`. These are not currently frozen due to difficulties matching versions on different platforms. On Raspberry Pi, it's best to specify `--only-binary=:all:` to ensure libraries like `numpy` and `scipy` are not compiled from source (which takes many hours, and/or fails). Pinning dependencies with `requirements.txt` and/or `requirements.in` may happen in the future.

## Creating releases

* Update the application's internal version number
  * Edit `pyproject.toml` to update the version number
* Update the changelog
* Git commit and git push
* Create a new version tag on GitLab (e.g. `v2.6.11`) that matches the `pyproject.toml` version number.
    * Make sure you prefix a lower case 'v', otherwise it won't be recognised as a release!
    * This tagging will trigger a CI pipeline that builds the JS client, tarballs up the server, and deploys it
        * Note: This also updates the build server's nginx redirect map file

## Changelog generation

* `npm install -g conventional-changelog-cli`
* `npx conventional-changelog -r 1 --config ./changelog.config.js -i CHANGELOG.md -s`

## Adding functionality

The microscope comprises a number of `Thing` instances, which provide actions and properties to implement hardware control and software features. These may be imported from any Python module, using `ofm_config.json`. See the LabThings-FastAPI documentation for how to create a `Thing`. 

Currently, the camera and stage classes are provided by external libraries, `labthings-picamera2` and `labthings-sangaboard`. Replacing these is the easiest way to use alternative hardware: interfaces are defined in `openflexure_microscope_server.things.camera` and `openflexure_microscope_server.things.stage` respectively.
